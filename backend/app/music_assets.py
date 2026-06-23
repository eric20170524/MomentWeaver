from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from .models import MusicCandidate, MusicSearchRequest, VideoPlan
from .settings import get_smart_asset_kit_path


class MusicAssetService:
    @property
    def kit_path(self) -> Path:
        return get_smart_asset_kit_path()

    async def search(self, request: MusicSearchRequest) -> List[MusicCandidate]:
        query = request.query.strip() or self._query_from_mood(request.mood)
        duration = int(request.duration_seconds)
        kit_exists = self.kit_path.exists()
        candidates = [
            MusicCandidate(
                id="sak-generate",
                title=f"SAK 生成配乐 · {request.mood}",
                source="smart-asset-kit",
                prompt=f"{query}，{duration} 秒左右，轻微律动，适合中文竖屏观点短视频，避免抢人声。",
                status="available" if kit_exists else "missing-smart-asset-kit",
                can_download=kit_exists,
                note="点击下载会调用 SAK 生成 mp3，完成后自动合成视频。" if kit_exists else "请先在设置里配置 SMART_ASSET_KIT_PATH。",
            ),
            MusicCandidate(
                id="ambient-warm",
                title="温暖轻电子",
                source="prompt-preset",
                prompt="温暖轻电子、柔和鼓点、克制铺底，适合观点表达和图文叙事。",
                status="prompt-only",
                can_download=kit_exists,
                note="使用这个提示词通过 SAK 生成并下载。",
            ),
            MusicCandidate(
                id="clean-documentary",
                title="干净纪实感",
                source="prompt-preset",
                prompt="干净钢琴与轻弦乐，稳定、有呼吸感，适合真实故事和朋友圈回顾。",
                status="prompt-only",
                can_download=kit_exists,
                note="使用这个提示词通过 SAK 生成并下载。",
            ),
        ]
        return candidates

    def prompt_from_plan(self, plan: VideoPlan, caption: str = "", mood: str = "warm") -> str:
        tone_map = {
            "documentary": "纪实感、克制、清晰叙事",
            "warm": "温暖、有希望感、轻柔推进",
            "cinematic": "电影感、层次渐进、开阔但不过度煽情",
            "sharp": "利落、科技感、节奏明确",
            "minimal": "极简、低存在感、适合阅读字幕",
        }
        shot_words = "；".join(shot.title for shot in plan.shots[:3] if shot.title)
        topic_words = "、".join(plan.hashtags[:3]) or "朋友圈图文成片"
        hook = plan.hook or (caption[:48] if caption else plan.title)
        tone = tone_map.get(plan.tone, tone_map.get(mood, tone_map["warm"]))
        return (
            f"{tone}的中文竖屏短视频背景音乐，主题围绕“{hook}”，"
            f"关键词：{topic_words}。镜头情绪：{shot_words or plan.title}。"
            "轻微律动，旋律不要抢戏，适合字幕阅读，避免使用任何版权歌曲名或艺人名。"
        )

    async def generate_with_sak(
        self,
        prompt: str,
        job_dir: Path,
        duration_seconds: float = 24.0,
        seamless: bool = True,
    ) -> Tuple[Path, str | None]:
        if not self.kit_path.exists():
            raise FileNotFoundError(f"smart-asset-kit not found: {self.kit_path}")

        out_path = job_dir / "music" / "bgm.mp3"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        python_bin = os.getenv("SAK_PYTHON", sys.executable or "python3")
        final_prompt = (
            f"{prompt}。时长约 {int(duration_seconds)} 秒，适合作为短视频背景音乐，"
            "音量不要压过中文字幕阅读节奏。"
        )
        cmd = [
            python_bin,
            "-m",
            "smart_asset_kit.cli.main",
            "gen-audio",
            final_prompt,
            "--out",
            str(out_path),
        ]
        if seamless:
            cmd.append("--seamless")

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{self.kit_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        def run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                cwd=str(self.kit_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=240,
            )

        result = await asyncio.to_thread(run)
        if result.returncode != 0 or not out_path.exists():
            detail = (result.stderr or result.stdout or "SAK did not create an audio file").strip()
            raise RuntimeError(detail[-1200:])
        warning = None
        if result.stderr.strip():
            warning = result.stderr.strip()[-600:]
        return out_path, warning

    @staticmethod
    def _query_from_mood(mood: str) -> str:
        mapping = {
            "warm": "温暖、轻电子、带一点希望感的背景音乐",
            "documentary": "纪实感、克制钢琴、轻微环境铺底的背景音乐",
            "cinematic": "电影感、渐进、开阔但不过度煽情的背景音乐",
            "sharp": "利落、科技感、节奏清晰的短视频背景音乐",
            "minimal": "极简、低存在感、适合阅读字幕的背景音乐",
        }
        return mapping.get(mood, mapping["warm"])
