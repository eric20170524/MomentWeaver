from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from typing import Iterable, List, Optional, Tuple

from .models import Shot, UploadedAsset, VideoPlan
from .settings import get_nebula_sdk_path


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _first_sentence(text: str, fallback: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return fallback
    parts = re.split(r"(?<=[。！？!?])", cleaned, maxsplit=1)
    return (parts[0] or cleaned)[:34]


def _split_caption(caption: str) -> List[str]:
    chunks = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", caption) if p.strip()]
    if chunks:
        return chunks[:8]
    sentences = [p.strip() for p in re.split(r"(?<=[。！？!?])", caption) if p.strip()]
    return sentences[:8] or ["把这条朋友圈重新讲成一个更适合短视频传播的故事。"]


def fallback_plan(
    caption: str,
    assets: Iterable[UploadedAsset],
    tone: str = "documentary",
    duration_seconds: float = 24.0,
) -> VideoPlan:
    images = list(assets)
    paragraphs = _split_caption(caption)
    shot_count = _clamp(max(len(images), min(len(paragraphs), 5), 3), 3, 7)
    shot_count = int(shot_count)
    target_duration = _clamp(duration_seconds or shot_count * 4.0, 12.0, 45.0)
    per_shot = round(target_duration / shot_count, 1)

    hook = _first_sentence(caption, "把朋友圈变成一支可转发的微视短片")
    title = hook.rstrip("。！？!?,，")[:18] or "朋友圈成片"
    motions = ["push_in", "slow_zoom", "pan_left", "pan_up", "still"]

    shots: List[Shot] = []
    for idx in range(shot_count):
        paragraph = paragraphs[idx % len(paragraphs)]
        image_index = idx % max(1, len(images))
        clean = re.sub(r"\s+", " ", paragraph).strip()
        title_seed = clean[:16].rstrip("，。,.")
        shots.append(
            Shot(
                id=f"shot-{idx + 1}",
                image_index=image_index,
                title=title_seed or f"镜头 {idx + 1}",
                caption=clean[:72] or "用画面把重点讲清楚。",
                duration=per_shot,
                motion=motions[idx % len(motions)],
                emphasis="保留朋友圈真实感，同时强化短视频节奏。",
            )
        )

    hashtags = ["朋友圈", "微视", "图文成片"]
    if "AI" in caption or "ai" in caption.lower():
        hashtags.insert(0, "AI")

    return VideoPlan(
        title=title,
        hook=hook,
        tone=tone if tone in {"cinematic", "documentary", "warm", "sharp", "minimal"} else "documentary",
        duration_seconds=round(sum(s.duration for s in shots), 1),
        music_query="温暖、有推进感、适合中文观点短视频的轻电子背景音乐",
        weishi_caption=f"{hook} #朋友圈 #微视 #图文成片",
        hashtags=hashtags,
        shots=shots,
    )


def _extract_json_object(raw: str) -> dict:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def _repair_plan(data: dict, fallback: VideoPlan, image_count: int, tone: str) -> VideoPlan:
    data = dict(data or {})
    data.setdefault("title", fallback.title)
    data.setdefault("hook", fallback.hook)
    data.setdefault("tone", tone)
    data.setdefault("aspect_ratio", "9:16")
    data.setdefault("duration_seconds", fallback.duration_seconds)
    data.setdefault("music_query", fallback.music_query)
    data.setdefault("weishi_caption", fallback.weishi_caption)
    data.setdefault("hashtags", fallback.hashtags)

    repaired_shots = []
    for index, shot in enumerate(data.get("shots") or []):
        if not isinstance(shot, dict):
            continue
        shot = dict(shot)
        shot.setdefault("id", f"shot-{index + 1}")
        shot.setdefault("title", fallback.shots[min(index, len(fallback.shots) - 1)].title)
        shot.setdefault("caption", fallback.shots[min(index, len(fallback.shots) - 1)].caption)
        shot.setdefault("duration", fallback.shots[min(index, len(fallback.shots) - 1)].duration)
        shot.setdefault("motion", "slow_zoom")
        shot.setdefault("emphasis", "")
        shot["image_index"] = int(shot.get("image_index", index)) % max(1, image_count)
        repaired_shots.append(shot)

    if not repaired_shots:
        repaired_shots = [s.dict() for s in fallback.shots]
    data["shots"] = repaired_shots[:8]
    return VideoPlan.parse_obj(data)


class NebulaStoryboardPlanner:
    def __init__(self) -> None:
        pass

    async def create_plan(
        self,
        caption: str,
        assets: List[UploadedAsset],
        tone: str = "documentary",
        duration_seconds: float = 24.0,
    ) -> Tuple[VideoPlan, bool, Optional[str]]:
        provider_name = os.getenv("NEBULA_PROVIDER", "openai")
        model_name = os.getenv("NEBULA_MODEL", "gpt-4o-mini")
        base_url = os.getenv("NEBULA_BASE_URL", "").strip()
        api_key = os.getenv("NEBULA_API_KEY", "").strip()
        fallback = fallback_plan(caption, assets, tone=tone, duration_seconds=duration_seconds)
        if not api_key:
            return fallback, False, "NEBULA_API_KEY is empty; used local storyboard fallback."

        try:
            nebula_sdk_path = get_nebula_sdk_path()
            if str(nebula_sdk_path) not in sys.path:
                sys.path.insert(0, str(nebula_sdk_path))
            from nebula_llm.factory import LLMFactory
            from nebula_llm.types import ModelInfo

            model = ModelInfo(
                target_model_id=model_name,
                provider=provider_name,
                type="text",
            )
            provider = LLMFactory.get_provider(model)
            prompt = self._build_prompt(caption, assets, tone, duration_seconds)
            options = {
                "temperature": 0.35,
                "system_prompt": "你是短视频导演和中文社交平台编辑，只输出严格 JSON。",
            }
            if base_url:
                options["base_url"] = base_url

            result = await provider.execute(
                model_config=model,
                api_key=api_key,
                prompt=prompt,
                options=options,
            )
            data = _extract_json_object(result.content or "")
            plan = _repair_plan(data, fallback, len(assets), tone)
            return plan, True, None
        except Exception as exc:
            return fallback, False, f"Nebula planner failed; used local fallback. Detail: {exc}"

    def _build_prompt(
        self,
        caption: str,
        assets: List[UploadedAsset],
        tone: str,
        duration_seconds: float,
    ) -> str:
        manifest = [
            {
                "image_index": i,
                "filename": asset.filename,
                "width": asset.width,
                "height": asset.height,
            }
            for i, asset in enumerate(assets)
        ]
        schema = {
            "title": "短标题",
            "hook": "开头 2 秒钩子",
            "tone": tone,
            "aspect_ratio": "9:16",
            "duration_seconds": duration_seconds,
            "music_query": "适合搜索或生成背景音乐的中文提示词",
            "weishi_caption": "可直接发微视的发布文案，带 2-4 个话题",
            "hashtags": ["话题1", "话题2"],
            "shots": [
                {
                    "id": "shot-1",
                    "image_index": 0,
                    "title": "镜头标题",
                    "caption": "屏幕字幕，不超过 36 个中文字符",
                    "duration": 3.5,
                    "motion": "push_in | slow_zoom | pan_left | pan_up | still",
                    "emphasis": "这一镜头的剪辑重点",
                }
            ],
        }
        return textwrap.dedent(
            f"""
            请把一条朋友圈内容改编为适合微视发布的 9:16 短视频分镜。

            要求：
            - 保留原文真实语气，不夸大事实，不编造人物关系和平台数据。
            - 节奏适合手机竖屏，开头 2 秒必须有观点或情绪钩子。
            - 每个镜头都要绑定一个 image_index，优先复用用户上传的图片。
            - 字幕要短，像真实短视频文案，不要官腔。
            - 背景音乐提示词要可用于搜索或生成，避免版权歌曲名和艺人名。
            - 总时长控制在 {duration_seconds:.0f} 秒左右。
            - 只输出 JSON，不输出解释。

            风格：{tone}
            图片清单：{json.dumps(manifest, ensure_ascii=False)}
            原始朋友圈文案：
            {caption}

            JSON 结构示例：
            {json.dumps(schema, ensure_ascii=False, indent=2)}
            """
        ).strip()
