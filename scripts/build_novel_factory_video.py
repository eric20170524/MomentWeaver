from __future__ import annotations

import json
import math
import os
import random
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.video_renderer import RESAMPLE, _font, _text_width, _wrap_text
from app.voiceover_sync import VoiceoverSegmentDuration, build_voiceover_timeline


ROOT = PROJECT_ROOT
JOB_ID = "novel_factory_100"
JOB_DIR = ROOT / "storage" / "jobs" / JOB_ID
SOURCE_DIR = JOB_DIR / "source"
MUSIC_DIR = JOB_DIR / "music"
VIDEO_DIR = JOB_DIR / "videos"
RENDER_DIR = JOB_DIR / "dynamic_render"
SCREENSHOT = SOURCE_DIR / "web_hero.png"

W, H = 1080, 1920
FPS = 15
FINAL_FPS = 30
TTS_PROVIDER = "minimax"
VOICE_NAME = "MiniMax scene-aware"
MINIMAX_VOICE_CATALOG = {
    "Yujie": {"voice": "Yujie", "voice_id": "female-yujie", "label": "MiniMax Yujie", "description": "mature magnetic narration"},
    "Tianmei": {"voice": "Tianmei", "voice_id": "female-tianmei", "label": "MiniMax Tianmei", "description": "warm sweet narration"},
    "Shaonv": {"voice": "Shaonv", "voice_id": "female-shaonv", "label": "MiniMax Shaonv", "description": "young energetic narration"},
}
MINIMAX_DEFAULT_VOICE = os.environ.get("MOMENTWEAVER_MINIMAX_VOICE", "Yujie").strip() or "Yujie"
MINIMAX_VOICE_MODE = os.environ.get("MOMENTWEAVER_MINIMAX_VOICE_MODE", "scene-aware").strip() or "scene-aware"
MINIMAX_TTS_SPEED = float(os.environ.get("MOMENTWEAVER_MINIMAX_TTS_SPEED", "1.1"))
SEGMENT_PAUSE = 1.15


def project_path_from_env(key: str, default: Path) -> Path:
    raw_value = os.environ.get(key, "").strip()
    if not raw_value:
        return default.resolve()
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


SMART_ASSET_KIT_PATH = project_path_from_env(
    "SMART_ASSET_KIT_PATH",
    PROJECT_ROOT / "lib" / "smart-asset-kit",
)

COLORS = ["#54d6ff", "#67e8a5", "#f8c76a", "#ff6f8e", "#b68cff", "#6ca8ff"]
INK = "#05070b"
WHITE = "#f8fafc"
MUTED = "#aeb8c8"
CYAN = "#54d6ff"
GREEN = "#67e8a5"
AMBER = "#f8c76a"
RED = "#ff6f8e"


STORIES = [
    (1, "数字仙途", 13, 56), (2, "灵脉烬土", 11, 54), (3, "火星洪荒", 13, 51), (4, "血统之刃", 11, 57),
    (5, "轮回服务器", 32, 150), (6, "因果飞升", 11, 55), (7, "渊墟潮生", 14, 62), (8, "时痕修正者", 11, 52),
    (9, "剑心代码", 12, 56), (10, "月阙飞升", 39, 188), (11, "飞升回收", 9, 40), (12, "极地契约", 14, 54),
    (13, "星核丹劫", 11, 54), (14, "天枢代码", 11, 51), (15, "虚拟天劫", 14, 52), (16, "气候仙尊", 10, 54),
    (17, "星骸神庭", 11, 55), (18, "基因锁仙根", 11, 50), (19, "一念万我", 32, 166), (20, "残骸渡魂", 12, 53),
    (21, "雨林禁域", 11, 51), (22, "月背仙宫", 33, 176), (23, "功德万界行", 12, 42), (24, "脑机超界", 14, 61),
    (25, "漠骨生春", 11, 45), (26, "恒星采集者", 11, 45), (27, "灵核协议", 12, 53), (28, "潮汐遗墟", 11, 46),
    (29, "星渊丹师", 12, 55), (30, "碎魂链", 12, 45), (31, "高原灵脉录", 14, 59), (32, "虫洞仙路", 9, 39),
    (33, "剑开新天", 12, 47), (34, "断水权", 29, 131), (35, "渊墟纪元", 15, 63), (36, "光年飞升", 12, 58),
    (37, "瑶光载道", 13, 48), (38, "灵土纪元", 8, 39), (39, "黑洞试炼", 12, 47), (40, "血脉反编译", 12, 50),
    (41, "梦境织雨", 11, 65), (42, "灵识彗星", 15, 61), (43, "双仙劫", 13, 60), (44, "长江灵脉", 13, 57),
    (45, "平行仙朝", 15, 66), (46, "蛊毒仙途", 9, 37), (47, "天风仙城", 12, 48), (48, "记忆篡位者", 36, 173),
    (49, "碳灵纪元", 11, 47), (50, "星舰灵源", 15, 54), (51, "万灵协议", 39, 174), (52, "珊瑚灵海", 11, 41),
    (53, "因果锚痕", 15, 57), (54, "义化剑歌", 9, 42), (55, "冰律极光庭", 10, 32), (56, "弦裂痕", 16, 75),
    (57, "灵墟源起", 13, 50), (58, "归乡异种", 13, 46), (59, "代码天书", 13, 61), (60, "熔心诀", 12, 51),
    (61, "三清悖论", 16, 63), (62, "舱内仙域", 16, 64), (63, "无形仙途", 12, 51), (64, "丝路仙途", 10, 40),
    (65, "永续配额", 4, 15), (66, "黑契灵石", 9, 38), (67, "光脑渡劫", 38, 171), (68, "雨林意志", 15, 91),
    (69, "寰阳仙轨", 11, 37), (70, "尘心仙劫", 13, 51), (71, "逆海灵渊", 9, 36), (72, "维度飞升", 16, 66),
    (73, "道心演天", 12, 52), (74, "灵枢快递", 16, 76), (75, "星脉契约", 10, 42), (76, "烙印呼吸", 9, 35),
    (77, "冰川魂魄", 11, 47), (78, "意志烙印", 10, 48), (79, "地球护卫舰", 10, 41), (80, "死境重生", 10, 42),
    (81, "深空寂静", 13, 45), (82, "钟鸣上海", 12, 62), (83, "漏能天劫", 31, 145), (84, "基因道侣", 10, 46),
    (85, "时笼之誓", 11, 44), (86, "核衍仙途", 30, 139), (87, "飞升直播", 14, 68), (88, "陨石仙缘", 13, 50),
    (89, "绝缘之证", 11, 45), (90, "泽灵仙途", 16, 85), (91, "镜像校准", 11, 52), (92, "合金仙骨", 13, 51),
    (93, "日蚀劫", 11, 53), (94, "移山诀", 10, 40), (95, "数据鬼域", 12, 50), (96, "灵环纪元", 12, 49),
    (97, "遗忘证道", 6, 26), (98, "时差千劫", 15, 81), (99, "掌中仙域", 13, 51), (100, "锚点纪元", 10, 40),
]


LIVE_PRESETS = [
    {
        "id": 22,
        "name": "月背仙宫",
        "draft": "广寒宫门开，弟子何在？月背钻探任务打开古仙遗迹，航天工程与修仙召唤在同一秒撞车。",
        "logs": ["context assembled for Novel #022", "planning nodes layout... success", "active drafting of Chapter 34 started"],
    },
    {
        "id": 5,
        "name": "轮回服务器",
        "draft": "死亡后意识被上传至仙界服务器，排行榜第一名太初仙尊的存活时间却永远为零。",
        "logs": ["initiating memory stream fetch", "found exception in section 7", "drafting next branch node for #005"],
    },
    {
        "id": 1,
        "name": "数字仙途",
        "draft": "程序员在全知系统第七区块发现十四行外部代码，脑机接口中长出第一条数字灵根。",
        "logs": ["credential distributed to Agent #001", "assembler context check passed", "generating prose stream"],
    },
    {
        "id": 67,
        "name": "光脑渡劫",
        "draft": "雷云在服务器上空凝聚，三十六重天劫算法加载完毕，代码成为迎战九天神罚的剑。",
        "logs": ["compiling thunder algorithms", "allocating compute units", "validator pass: context consistent"],
    },
]


SEGMENTS = [
    {
        "title": "100 部小说",
        "subtitle": "由 AI 全链路推进",
        "body": "这不是炫技页面，是一座正在冒烟的小说工厂：数字狂跳，Agent 续写，100 个世界同时开机。",
        "tag": "LIVE HERO",
        "min_duration": 31.0,
        "narration": "如果一个网页告诉你：一百部小说，正在由 AI 全链路推进，你会以为这是一个概念演示。但这个首屏真正抓人的地方，是它像一个运行中的战情室：星图在漂移，计数器在递增，Agent 正在续写章节。它展示的不是一句提示词，而是一条小说生产线正在工作。",
    },
    {
        "title": "主题本质",
        "subtitle": "从提示词，到生产协议",
        "body": "别再只问“AI 会不会写一段”。真正的变化是：灵感被拆成协议，创作开始被工业化。",
        "tag": "THEME",
        "min_duration": 21.0,
        "narration": "所以，这个主题真正有意思的地方，不是 AI 写了几段文字，而是它把小说创作拆成了生产协议。从一百个赛博修仙题材开始，系统先吸收趋势，再展开灵感会谈，再生成主线、目录、章节任务，最后校验、修复、导出、评估。",
    },
    {
        "title": "一组生产数据",
        "subtitle": "100 / 1409 / 623 万",
        "body": "100 本、1409 章、623 万级字符。可怕的不是数量，而是故事已经开始批量出生。",
        "tag": "RUN SUMMARY",
        "min_duration": 22.0,
        "narration": "页面给出的核心数据很直观：一百个小说项目全部进入创作入口，已发布章节超过一千四百章，导出口径字符量达到六百二十三万级，平均综合分七十四点六五。这意味着它讨论的不是单次生成，而是连续生产。",
    },
    {
        "title": "流水线怎么工作",
        "subtitle": "趋势吸收 → 灵感会谈 → 主线规划",
        "body": "趋势、灵感、主线、目录、续写、评估一路推进。写作不再等灵感，而是被送上流水线。",
        "tag": "PIPELINE",
        "min_duration": 25.0,
        "narration": "这条流水线分成六步：趋势吸收、灵感会谈、主线规划、目录生成、并发续写、导出评估。它的关键不是让模型凭空续写，而是把长篇写作拆成一个个可以排队、可以重试、可以恢复的任务节点。",
    },
    {
        "title": "AI 写作操作系统",
        "subtitle": "上下文、验证器、调度器、评估器",
        "body": "上下文守住记忆，验证器拦住跑偏，调度器让百本并发。AI 开始像编辑部一样运转。",
        "tag": "SYSTEM",
        "min_duration": 24.0,
        "narration": "更准确地说，它像一个 AI 写作操作系统。上下文装配器负责记住前文和设定，验证器负责检查章节有没有跑偏，调度器负责在一百本书之间分配任务槽位，评估器则负责把结果转成下一轮筛选依据。",
    },
    {
        "title": "三个高钩子样本",
        "subtitle": "月背仙宫 / 轮回服务器 / 数字仙途",
        "body": "月背仙宫、轮回服务器、数字灵根。这些不是书名，是能把读者拖进坑里的世界入口。",
        "tag": "STORY NODES",
        "min_duration": 25.0,
        "narration": "样本里最有画面感的是月背仙宫：月背钻探打开古仙遗迹，航天工程和修仙召唤撞在同一秒。轮回服务器把死亡意识上传、仙界排行榜、太初仙尊存活时间为零组合在一起。数字仙途则像程序员神话：脑机接口里长出数字灵根。",
    },
    {
        "title": "评估才是第二引擎",
        "subtitle": "写完以后，还要读懂自己写出了什么",
        "body": "写完只是开始。分数会决定谁被孵化、谁被重写、谁被淘汰，创作开始有了冷酷筛选。",
        "tag": "EVALUATION",
        "min_duration": 22.0,
        "narration": "所以评估矩阵很关键。开篇、人物、节奏、设定、市场潜力，被拆成结构化分数。头部项目继续孵化，普通项目进入重写或沉淀。AI 写作正在从灵感工具，走向内容供应链。",
    },
    {
        "title": "最终问题",
        "subtitle": "当创意可以并发",
        "body": "当创意可以并发，真正稀缺的不是手速，而是谁能选中那个会爆的开局。",
        "tag": "CLOSING",
        "min_duration": 22.0,
        "narration": "当然，批量并不等于精品。长篇仍然需要情绪递进、人物记忆、风格稳定和人工判断。真正有价值的，是让 AI 先跑出一百条路，再让人选择哪一条值得深挖。这个页面展示的不是一百个标题，而是一种新的创作基础设施。",
    },
]


SCENES: list[tuple[float, float, str, str, str, str]] = []
VOICE_SEGMENTS: list[dict[str, object]] = []
for segment, timing in zip(
    SEGMENTS,
    build_voiceover_timeline(
        [
            VoiceoverSegmentDuration(
                id=f"segment-{index:02d}",
                duration_seconds=0,
                pause_seconds=SEGMENT_PAUSE,
                minimum_scene_seconds=float(segment["min_duration"]),
            )
            for index, segment in enumerate(SEGMENTS, start=1)
        ],
        default_pause_seconds=SEGMENT_PAUSE,
    ),
):
    SCENES.append((timing.start, timing.end, str(segment["title"]), str(segment["subtitle"]), str(segment["body"]), str(segment["tag"])))


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "command failed")[-2500:])


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:])
    return float(result.stdout.strip())


def quote_ffconcat(path: Path) -> str:
    escaped = str(path.resolve()).replace("\\", "\\\\").replace("'", "\\'")
    return f"file '{escaped}'\n"


def resolve_minimax_voice(voice_name: str) -> dict[str, str]:
    preset = MINIMAX_VOICE_CATALOG.get(voice_name)
    if preset:
        return {key: str(value) for key, value in preset.items()}
    return {
        "voice": voice_name,
        "voice_id": voice_name,
        "label": f"MiniMax {voice_name}",
        "description": "custom MiniMax voice selected by environment",
    }


def minimax_voice_for_segment(segment: dict[str, object], index: int) -> dict[str, str]:
    if MINIMAX_VOICE_MODE == "single":
        return resolve_minimax_voice(MINIMAX_DEFAULT_VOICE)
    tag = str(segment.get("tag") or "")
    if tag in {"LIVE HERO", "STORY NODES"}:
        return resolve_minimax_voice("Shaonv")
    if tag in {"THEME", "CLOSING"}:
        return resolve_minimax_voice("Tianmei")
    return resolve_minimax_voice(MINIMAX_DEFAULT_VOICE)


def safe_voice_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_") or "minimax"


def load_minimax_audio_config() -> tuple[str, str]:
    config_path = SMART_ASSET_KIT_PATH / ".sak_config.json"
    data = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = str(data.get("minimax_api_key") or os.environ.get("MINIMAX_API_KEY") or "").strip()
    model = str(data.get("minimax_audio_model") or "speech-2.8-hd").strip()
    if not api_key:
        raise RuntimeError("MiniMax API key is not configured in Smart Asset Kit.")
    return api_key, model


def generate_tts_segment(text_value: str, out_path: Path, voice: dict[str, str]) -> None:
    if TTS_PROVIDER != "minimax":
        raise RuntimeError(f"Unsupported TTS provider: {TTS_PROVIDER}")
    api_key, model = load_minimax_audio_config()
    payload = {
        "model": model,
        "text": text_value,
        "voice_setting": {
            "voice_id": voice["voice_id"],
            "speed": MINIMAX_TTS_SPEED,
            "vol": 1,
            "pitch": 0,
            "english_normalization": False,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "output_format": "hex",
    }
    request = urllib.request.Request(
        "https://api.minimaxi.com/v1/t2a_v2",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiniMax TTS failed ({exc.code}): {detail}") from exc
    status = result.get("base_resp", {}).get("status_code", 0)
    if status != 0:
        raise RuntimeError(f"MiniMax TTS error: {result.get('base_resp', {}).get('status_msg')}")
    audio_hex = result.get("data", {}).get("audio")
    if not audio_hex:
        raise RuntimeError(f"MiniMax TTS returned no audio data: {result}")
    out_path.write_bytes(bytes.fromhex(audio_hex))


def ease_out_cubic(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


def ease_in_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha)


def alpha_layer(size: tuple[int, int], opacity: float, color: str = "#000000") -> Image.Image:
    return Image.new("RGBA", size, hex_to_rgba(color, int(255 * opacity)))


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    size: int,
    fill: str = WHITE,
    stroke: int = 0,
    stroke_fill: str = "#000000",
    anchor: str | None = None,
) -> None:
    draw.text(xy, value, font=_font(size), fill=fill, stroke_width=stroke, stroke_fill=stroke_fill, anchor=anchor)


def wrapped_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    size: int,
    max_width: int,
    fill: str = WHITE,
    line_gap: int = 12,
    max_lines: int = 4,
    stroke: int = 0,
) -> int:
    font = _font(size)
    lines = _wrap_text(draw, value, font, max_width, max_lines)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke, stroke_fill="#000000")
        bbox = draw.textbbox((x, y), line, font=font, stroke_width=stroke)
        y = bbox[3] + line_gap
    return y


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int] | str,
    outline: tuple[int, int, int, int] | str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def make_base_background() -> Image.Image:
    if SCREENSHOT.exists():
        source = Image.open(SCREENSHOT).convert("RGB")
        bg = source.resize((W, H), RESAMPLE).filter(ImageFilter.GaussianBlur(4)).convert("RGBA")
        dim = alpha_layer((W, H), 0.52, "#05070b")
        return Image.alpha_composite(bg, dim)
    return Image.new("RGBA", (W, H), hex_to_rgba("#05070b"))


BASE_BG = make_base_background()
NODE_SEED = random.Random(20260630)
NODE_PHASES = [NODE_SEED.random() * math.tau for _ in STORIES]


def draw_gradient_grid(frame: Image.Image, t: float) -> None:
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay, "RGBA")
    for y in range(0, H, 3):
        k = y / H
        r = int(5 + 12 * k)
        g = int(7 + 18 * k)
        b = int(13 + 44 * k)
        od.rectangle((0, y, W, y + 3), fill=(r, g, b, 54))
    offset = int((t * 18) % 96)
    for x in range(-offset, W, 96):
        od.line((x, 0, x, H), fill=(125, 211, 252, 20), width=1)
    for y in range(-offset, H, 96):
        od.line((0, y, W, y), fill=(125, 211, 252, 14), width=1)
    frame.alpha_composite(overlay)


def projected_nodes(t: float) -> list[dict[str, float | int | str]]:
    nodes = []
    for index, (story_id, title, chapters, chars) in enumerate(STORIES):
        turn = index * 2.399963
        radius = 0.1 + math.sqrt(index / len(STORIES)) * 0.44
        base_x = 0.62 + math.cos(turn) * radius
        base_y = 0.48 + math.sin(turn) * radius * 0.76
        pulse = math.sin(t * 0.95 + index * 0.7) * 0.008
        drift = math.cos(t * (0.35 + (index % 7) * 0.08) + index) * 0.012
        nodes.append(
            {
                "id": story_id,
                "title": title,
                "chapters": chapters,
                "chars": chars,
                "x": (base_x + pulse) * W,
                "y": (base_y + drift) * H,
                "size": 2.4 + min(chapters, 40) * 0.18,
                "color": COLORS[index % len(COLORS)],
            }
        )
    return nodes


def draw_star_map(frame: Image.Image, t: float, active_id: int | None = None, opacity: float = 1.0) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    nodes = projected_nodes(t)

    for i, a in enumerate(nodes):
        for j in range(i + 1, len(nodes), 11):
            b = nodes[j]
            dx = float(a["x"]) - float(b["x"])
            dy = float(a["y"]) - float(b["y"])
            distance = math.hypot(dx, dy)
            if distance < 175:
                alpha = int((58 * (1 - distance / 175)) * opacity)
                if int(a["id"]) == active_id or int(b["id"]) == active_id:
                    alpha = int(min(160, alpha + 80))
                draw.line((float(a["x"]), float(a["y"]), float(b["x"]), float(b["y"])), fill=hex_to_rgba(str(a["color"]), alpha), width=1)

    for index, node in enumerate(nodes):
        x, y = float(node["x"]), float(node["y"])
        size = float(node["size"])
        color = str(node["color"])
        active = int(node["id"]) == active_id
        glow = int(50 * opacity) if active else int(24 * opacity)
        if active:
            r = size + 14 + math.sin(t * 5) * 5
            draw.ellipse((x - r, y - r, x + r, y + r), outline=hex_to_rgba(color, 120), width=3)
        draw.ellipse((x - size - 5, y - size - 5, x + size + 5, y + size + 5), fill=hex_to_rgba(color, max(0, glow)))
        draw.ellipse((x - size, y - size, x + size, y + size), fill=hex_to_rgba(color, int(210 * opacity)))
        if index % 13 == 0:
            text(draw, (int(x + 10), int(y - 13)), f"{int(node['id']):03d}", 18, fill="#cbd5e1")

    frame.alpha_composite(layer)


def current_live_preset(t: float) -> tuple[dict[str, object], float]:
    cycle = 10.5
    index = int(t // cycle) % len(LIVE_PRESETS)
    return LIVE_PRESETS[index], (t % cycle) / cycle


def draw_topbar(draw: ImageDraw.ImageDraw) -> None:
    rounded_rect(draw, (44, 20, 82, 58), 8, fill=(255, 255, 255, 34), outline=(255, 255, 255, 60), width=1)
    text(draw, (55, 27), "堆", 21, fill="#ffffff")
    text(draw, (92, 25), "堆浪", 23, fill="#ffffff")
    for x, label in [(790, "链路"), (870, "样本"), (950, "评估"), (1020, "官网")]:
        text(draw, (x, 28), label, 19, fill="#cbd5e1")


def draw_metric(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], value: str, label: str, flash: float = 0) -> None:
    fill_alpha = 32 + int(28 * flash)
    rounded_rect(draw, box, 0, fill=(3, 8, 15, fill_alpha), outline=(255, 255, 255, 42), width=1)
    color = "#ffffff" if flash <= 0 else "#67e8a5"
    text(draw, (box[0] + 20, box[1] + 28), value, 54, fill=color)
    text(draw, (box[0] + 20, box[1] + 96), label, 24, fill="#cbd5e1")


def draw_console(frame: Image.Image, t: float, x: int = 566, y: int = 720) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    w, h = 460, 558
    rounded_rect(draw, (x, y, x + w, y + h), 8, fill=(7, 12, 19, 215), outline=(255, 255, 255, 48), width=1)
    draw.rectangle((x, y + 50, x + w, y + 51), fill=(255, 255, 255, 38))
    draw.ellipse((x + 20, y + 19, x + 32, y + 31), fill=hex_to_rgba(GREEN))
    text(draw, (x + 44, y + 15), "RUN SUMMARY", 18, fill="#cbd5e1")

    progress = ease_out_cubic(min(1, t / 1.3))
    chapters = int(1409 * progress) + max(0, int((t - 13) // 11))
    chars = int(623 * progress) + max(0, int((t - 16) // 18))
    flashes = [0, max(0, 1 - ((t - 13) % 11) / 1.2) if t > 13 else 0, max(0, 1 - ((t - 16) % 18) / 1.2) if t > 16 else 0, 0]
    metrics = [(int(100 * progress), "小说项目"), (chapters, "已发布章节"), (chars, "万字级字符"), (int(91 * progress), "高峰活跃任务")]
    for idx, (value, label) in enumerate(metrics):
        bx = x + (idx % 2) * 230
        by = y + 51 + (idx // 2) * 136
        draw_metric(draw, (bx, by, bx + 230, by + 136), f"{value:,}", label, flashes[idx])

    preset, local = current_live_preset(t)
    monitor_y = y + 323
    draw.rectangle((x, monitor_y, x + w, monitor_y + 112), fill=(0, 0, 0, 76))
    rounded_rect(draw, (x + 18, monitor_y + 14, x + 112, monitor_y + 40), 5, fill=(84, 214, 255, 32), outline=(84, 214, 255, 92), width=1)
    text(draw, (x + 28, monitor_y + 18), "LIVE DRAFTING", 14, fill=CYAN)
    text(draw, (x + 260, monitor_y + 18), f"Agent #{int(preset['id']):03d} [{preset['name']}]", 16, fill="#cbd5e1")
    draft = str(preset["draft"])
    char_count = min(len(draft), max(0, int((local * 1.22 - 0.12) * len(draft))))
    typed = draft[:char_count]
    wrapped_text(draw, (x + 18, monitor_y + 56), typed, 19, 410, fill="#f8fafc", line_gap=6, max_lines=2)
    if int(t * 2) % 2 == 0:
        draw.rectangle((x + 392, monitor_y + 86, x + 399, monitor_y + 104), fill=hex_to_rgba(CYAN))

    log_y = y + 435
    draw.rectangle((x, log_y, x + w, y + h), fill=(255, 255, 255, 10))
    logs: list[str] = list(preset["logs"])  # type: ignore[arg-type]
    base_second = 18 + int(t) % 40
    for idx, msg in enumerate(logs):
        yy = log_y + 20 + idx * 36
        alpha = 255 if local > 0.08 + idx * 0.12 else 70
        text(draw, (x + 18, yy), f"17:{14 + int(t // 60):02d}:{base_second + idx:02d}", 18, fill=AMBER)
        text(draw, (x + 105, yy), f"[AGENT] {msg}", 17, fill="#cbd5e1" if alpha > 100 else "#64748b")


def draw_hero(frame: Image.Image, t: float) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    active, _ = current_live_preset(t)
    draw_gradient_grid(frame, t)
    draw_star_map(frame, t, active_id=int(active["id"]), opacity=1.0)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade, "RGBA")
    for x in range(W):
        alpha = int(190 - 110 * (x / W))
        sd.line((x, 72, x, H), fill=(5, 7, 11, max(40, alpha)))
    frame.alpha_composite(shade)
    draw_topbar(draw)
    text(draw, (54, 1220), "AUTONOMOUS NOVEL FACTORY / 2026 PRODUCTION RUN", 20, fill=CYAN)
    wrapped_text(draw, (54, 1262), "100 部小说，\n由 AI 全链路推进。", 82, 545, fill=WHITE, line_gap=10, max_lines=3, stroke=2)
    wrapped_text(draw, (54, 1580), "从 100 个赛博修仙题材切入，自动完成灵感探讨、主线规划、目录生成、章节续写、校验修复、导出评估。", 29, 690, fill="#cbd5e1", line_gap=13, max_lines=4)
    rounded_rect(draw, (54, 1772, 204, 1822), 8, fill=(84, 214, 255, 230))
    text(draw, (74, 1785), "查看自动化链路", 21, fill="#031016")
    rounded_rect(draw, (218, 1772, 356, 1822), 8, fill=(255, 255, 255, 20), outline=(255, 255, 255, 72))
    text(draw, (238, 1785), "查看小说节点", 21, fill=WHITE)
    draw_console(frame, t)


def scene_for_time(t: float) -> tuple[int, tuple[int, int, str, str, str, str]]:
    for index, scene in enumerate(SCENES):
        start, end = scene[0], scene[1]
        if start <= t < end:
            return index, scene
    return len(SCENES) - 1, SCENES[-1]


def draw_pipeline(draw: ImageDraw.ImageDraw, t: float, start: float) -> None:
    labels = ["趋势吸收", "灵感会谈", "主线规划", "目录生成", "并发续写", "导出评估"]
    y = 1025
    for idx, label in enumerate(labels):
        x = 74 + idx * 160
        p = ease_out_cubic((t - start - idx * 0.35) / 0.8)
        if p <= 0:
            continue
        alpha = int(220 * p)
        rounded_rect(draw, (x, y, x + 124, y + 92), 8, fill=(12, 18, 28, int(185 * p)), outline=(84, 214, 255, alpha // 2), width=2)
        text(draw, (x + 18, y + 15), f"{idx + 1:02d}", 23, fill=CYAN)
        text(draw, (x + 18, y + 52), label, 23, fill=WHITE)
        if idx < len(labels) - 1:
            line_p = ease_out_cubic((t - start - idx * 0.35 - 0.25) / 0.6)
            draw.line((x + 126, y + 46, x + 126 + int(34 * line_p), y + 46), fill=hex_to_rgba(GREEN, int(190 * line_p)), width=3)


def draw_metrics_panel(draw: ImageDraw.ImageDraw, t: float, start: float) -> None:
    vals = [("100 / 100", "创作入口"), ("6,233,743", "导出字符"), ("74.65", "平均综合分"), ("39 章", "最高单书进度")]
    for idx, (value, label) in enumerate(vals):
        x = 92 + (idx % 2) * 452
        y = 1030 + (idx // 2) * 150
        p = ease_out_cubic((t - start - idx * 0.28) / 0.8)
        rounded_rect(draw, (x, y, x + 390, y + 116), 8, fill=(10, 15, 23, int(190 * p)), outline=(255, 255, 255, int(62 * p)), width=1)
        text(draw, (x + 25, y + 22), label, 25, fill=CYAN if idx == 0 else [AMBER, GREEN, RED][(idx - 1) % 3])
        text(draw, (x + 25, y + 58), value, 44, fill=WHITE)


def draw_system_panel(draw: ImageDraw.ImageDraw, t: float, start: float) -> None:
    modules = [("创作中枢", 0.84), ("上下文装配器", 0.66), ("验证器", 0.78), ("调度器", 0.9), ("评估器", 0.72)]
    for idx, (label, score) in enumerate(modules):
        x = 90
        y = 1015 + idx * 94
        p = ease_out_cubic((t - start - idx * 0.22) / 0.7)
        rounded_rect(draw, (x, y, x + 900, y + 58), 8, fill=(11, 17, 26, int(170 * p)), outline=(255, 255, 255, int(44 * p)), width=1)
        text(draw, (x + 22, y + 16), label, 25, fill=WHITE)
        bar_w = int(470 * score * p * (0.96 + 0.04 * math.sin(t * 3 + idx)))
        draw.rounded_rectangle((x + 350, y + 18, x + 350 + bar_w, y + 38), radius=10, fill=hex_to_rgba(COLORS[idx], int(230 * p)))


def draw_story_cards(draw: ImageDraw.ImageDraw, t: float, start: float) -> None:
    cards = [
        ("#022", "月背仙宫", "月背钻探打开古仙遗迹，航天工程与修仙召唤撞车。"),
        ("#005", "轮回服务器", "死亡意识上传仙界服务器，排行榜第一的存活时间为 0。"),
        ("#001", "数字仙途", "十四行外部代码，让脑机接口长出第一条数字灵根。"),
    ]
    for idx, (num, title, body) in enumerate(cards):
        x = 82
        y = 970 + idx * 190
        p = ease_out_cubic((t - start - idx * 0.35) / 0.8)
        offset = int((1 - p) * 80)
        rounded_rect(draw, (x + offset, y, 998 + offset, y + 150), 8, fill=(11, 17, 26, int(205 * p)), outline=(84, 214, 255, int(70 * p)), width=1)
        text(draw, (x + 26 + offset, y + 20), num, 26, fill=AMBER)
        text(draw, (x + 118 + offset, y + 16), title, 38, fill=WHITE)
        wrapped_text(draw, (x + 26 + offset, y + 72), body, 25, 850, fill="#dbeafe", line_gap=8, max_lines=2)


def draw_ranking(draw: ImageDraw.ImageDraw, t: float, start: float) -> None:
    rows = [("01", "月背仙宫", "86"), ("02", "轮回服务器", "89"), ("03", "一念万我", "87"), ("04", "光脑渡劫", "86")]
    cx, cy, r = 240, 1060, 126
    arc_p = ease_out_cubic((t - start) / 1.5)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 40), width=16)
    draw.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + int(270 * arc_p), fill=hex_to_rgba(GREEN), width=16)
    text(draw, (cx, cy - 36), "74.65", 58, fill=WHITE, anchor="mm")
    text(draw, (cx, cy + 28), "AVG OVERALL", 22, fill=MUTED, anchor="mm")
    for idx, row in enumerate(rows):
        y = 1240 + idx * 72
        p = ease_out_cubic((t - start - idx * 0.2) / 0.8)
        rounded_rect(draw, (90, y, 990, y + 55), 8, fill=(10, 15, 23, int(190 * p)), outline=(255, 255, 255, int(40 * p)), width=1)
        text(draw, (120, y + 13), row[0], 24, fill=CYAN)
        text(draw, (190, y + 10), row[1], 29, fill=WHITE)
        text(draw, (890, y + 10), row[2], 30, fill=GREEN)


def draw_regular_scene(frame: Image.Image, t: float, index: int, scene: tuple[int, int, str, str, str, str]) -> None:
    start, end, title, subtitle, body, tag = scene
    draw_gradient_grid(frame, t)
    active_ids = [22, 5, 1, 67, 48, 19]
    active = active_ids[int(t // 7) % len(active_ids)]
    draw_star_map(frame, t, active_id=active, opacity=0.78)
    shade = alpha_layer((W, H), 0.5, "#05070b")
    frame.alpha_composite(shade)
    draw = ImageDraw.Draw(frame, "RGBA")
    p = ease_out_cubic((t - start) / 1.0)
    y_shift = int((1 - p) * 46)
    text(draw, (66, 158 + y_shift), tag, 24, fill=CYAN)
    wrapped_text(draw, (66, 208 + y_shift), title, 72, 900, fill=WHITE, line_gap=14, max_lines=2, stroke=2)
    wrapped_text(draw, (66, 392 + y_shift), subtitle, 42, 900, fill="#e2e8f0", line_gap=14, max_lines=2)
    rounded_rect(draw, (66, 535 + y_shift, 1014, 760 + y_shift), 8, fill=(10, 15, 23, 195), outline=(255, 255, 255, 50), width=1)
    wrapped_text(draw, (102, 578 + y_shift), body, 34, 872, fill="#f8fafc", line_gap=18, max_lines=4)
    draw.line((66, 830, 1014, 830), fill=hex_to_rgba(CYAN, 80), width=2)
    progress = (t - start) / max(1, end - start)
    draw.line((66, 830, 66 + int(948 * progress), 830), fill=hex_to_rgba(GREEN, 210), width=5)

    if tag == "RUN SUMMARY":
        draw_metrics_panel(draw, t, start)
    elif tag == "PIPELINE":
        draw_pipeline(draw, t, start)
    elif tag == "SYSTEM":
        draw_system_panel(draw, t, start)
    elif tag == "STORY NODES":
        draw_story_cards(draw, t, start)
    elif tag == "EVALUATION":
        draw_ranking(draw, t, start)
    elif tag == "CLOSING":
        wrapped_text(draw, (110, 1045), "不是一百个标题，\n而是一座小说试验工厂。", 66, 860, fill=WHITE, line_gap=18, max_lines=3, stroke=2)


def draw_frame(t: float, duration: float) -> Image.Image:
    frame = BASE_BG.copy()
    index, scene = scene_for_time(t)
    if index == 0:
        draw_hero(frame, t)
    else:
        draw_regular_scene(frame, t, index, scene)
    draw = ImageDraw.Draw(frame, "RGBA")
    text(draw, (70, 1860), "#AI写作  #赛博修仙  #内容生产线", 25, fill="#dbeafe", stroke=1)
    text(draw, (822, 1860), "MomentWeaver", 25, fill="#dbeafe", stroke=1)
    return Image.alpha_composite(BASE_BG.copy(), frame).convert("RGB")


def build_audio() -> tuple[Path, float]:
    global SCENES, VOICE_SEGMENTS

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    segments_dir = MUSIC_DIR / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    narration = MUSIC_DIR / "narration_segmented.wav"
    mixed = MUSIC_DIR / "bgm.wav"
    concat_path = segments_dir / "narration.ffconcat"

    concat_items: list[Path] = []
    generated_segments: list[tuple[dict[str, object], Path, int]] = []
    measured_segments: list[VoiceoverSegmentDuration] = []
    VOICE_SEGMENTS = []

    for index, segment in enumerate(SEGMENTS, start=1):
        voice = minimax_voice_for_segment(segment, index)
        mp3 = segments_dir / f"segment_{index:02d}_minimax_{safe_voice_name(voice['voice'])}.mp3"
        wav = segments_dir / f"segment_{index:02d}.wav"
        text_value = str(segment["narration"])

        generate_tts_segment(text_value, mp3, voice=voice)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(wav)])
        voice_duration = probe_duration(wav)
        generated_segments.append((segment, wav, index))
        VOICE_SEGMENTS.append(
            {
                "segment_id": f"segment-{index:02d}",
                "tag": segment.get("tag"),
                "voice": voice["voice"],
                "voice_id": voice["voice_id"],
                "label": voice["label"],
                "description": voice["description"],
                "provider": "minimax",
                "speed": MINIMAX_TTS_SPEED,
            }
        )
        measured_segments.append(
            VoiceoverSegmentDuration(
                id=f"segment-{index:02d}",
                duration_seconds=voice_duration,
                pause_seconds=SEGMENT_PAUSE,
                minimum_scene_seconds=float(segment["min_duration"]),
            )
        )

    timings = build_voiceover_timeline(measured_segments, default_pause_seconds=SEGMENT_PAUSE)
    SCENES = [
        (timing.start, timing.end, str(segment["title"]), str(segment["subtitle"]), str(segment["body"]), str(segment["tag"]))
        for (segment, _wav, _index), timing in zip(generated_segments, timings)
    ]

    for (_segment, wav, index), timing in zip(generated_segments, timings):
        silence = segments_dir / f"silence_{index:02d}.wav"
        run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-t",
                f"{timing.pause_duration:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-c:a",
                "pcm_s16le",
                str(silence),
            ]
        )
        concat_items.extend([wav, silence])

    with concat_path.open("w", encoding="utf-8") as handle:
        handle.write("ffconcat version 1.0\n")
        for item in concat_items:
            handle.write(quote_ffconcat(item))

    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(narration)])
    total_duration = probe_duration(narration)
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(narration),
            "-f",
            "lavfi",
            "-t",
            f"{total_duration:.3f}",
            "-i",
            "sine=frequency=88:sample_rate=44100",
            "-f",
            "lavfi",
            "-t",
            f"{total_duration:.3f}",
            "-i",
            "sine=frequency=176:sample_rate=44100",
            "-f",
            "lavfi",
            "-t",
            f"{total_duration:.3f}",
            "-i",
            "anoisesrc=color=pink:sample_rate=44100",
            "-filter_complex",
            "[0:a]volume=1.05[voice];[1:a]volume=0.024[low];[2:a]volume=0.011[mid];[3:a]volume=0.007,lowpass=f=900[noise];"
            "[voice][low][mid][noise]amix=inputs=4:duration=longest:dropout_transition=2,alimiter=limit=0.95[out]",
            "-map",
            "[out]",
            "-t",
            f"{total_duration:.3f}",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(mixed),
        ]
    )
    return mixed, total_duration


def render_video_stream(duration: float) -> Path:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    silent = RENDER_DIR / "novel_factory_dynamic_no_audio.mp4"
    total_frames = int(math.ceil(duration * FPS))
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-vf",
        f"fps={FINAL_FPS},format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-movflags",
        "+faststart",
        str(silent),
    ]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    for frame_index in range(total_frames):
        t = frame_index / FPS
        frame = draw_frame(t, duration)
        proc.stdin.write(frame.tobytes())
        if frame_index % (FPS * 10) == 0:
            print(f"rendered {frame_index}/{total_frames} frames ({t:.1f}s)")
    proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise RuntimeError(stderr[-2500:])
    return silent


def mux_audio(silent: Path, audio: Path) -> Path:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    final = VIDEO_DIR / f"{JOB_ID}_weishi_dynamic.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(silent),
            "-i",
            str(audio),
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )
    return final


def write_metadata(final: Path, duration: float) -> None:
    project = {
        "title": "100 部小说：AI 全链路创作战情室",
        "description": "分析堆浪 100 部小说自动创作主题的 3-5 分钟微视视频，保留首屏动态战情室效果。",
        "source_url": "https://dl.chuangyi.chat/100-novels.html",
        "renderer": "MomentWeaver dynamic frame renderer",
        "tts_provider": TTS_PROVIDER,
        "tts_backend": "minimax-http",
        "tts_speed": MINIMAX_TTS_SPEED,
        "voice_name": VOICE_NAME,
        "voice_policy": {
            "provider": "minimax",
            "mode": MINIMAX_VOICE_MODE,
            "default_voice": MINIMAX_DEFAULT_VOICE,
            "default_speed": MINIMAX_TTS_SPEED,
            "allow_other_minimax_voices": True,
            "system_voice_for_release": False,
            "macos_say_for_release": False,
        },
        "voice_segments": VOICE_SEGMENTS,
        "audio_mode": "segmented narration with scene pauses",
        "timelineDuration": round(duration, 3),
        "canvas": {"width": W, "height": H, "aspect_ratio": "9:16"},
        "scenes": [
            {"start": s, "end": e, "title": title, "subtitle": subtitle, "body": body, "tag": tag}
            for s, e, title, subtitle, body, tag in SCENES
        ],
    }
    publish = {
        "title": project["title"],
        "short_title": "100 部 AI 小说工厂",
        "caption": "100 部小说由 AI 全链路推进：这不是单次生成，而是内容生产线。",
        "video_description": "一百部小说同时开工，AI 不再只是帮你写一段，而是在运行一座小说工厂：选题、主线、目录、续写、校验、评估全链路推进。这个视频拆解堆浪战情室背后的核心变化：内容创作正在从灵感工具，升级为可调度、可筛选、可复盘的生产基础设施。",
        "hashtags": ["AI写作", "赛博修仙", "内容生产线", "MomentWeaver"],
        "video_path": str(final.resolve()),
        "duration_seconds": round(duration, 3),
        "voice_name": VOICE_NAME,
        "voice_policy": project["voice_policy"],
        "tts_backend": "minimax-http",
        "tts_speed": MINIMAX_TTS_SPEED,
    }
    status = {
        "job_id": JOB_ID,
        "status": "rendered",
        "video_path": str(final.resolve()),
        "video_url": f"/api/jobs/{JOB_ID}/video/{final.name}",
        "project_path": str((JOB_DIR / "visual_project.json").resolve()),
        "status_path": str((JOB_DIR / "render_status.json").resolve()),
    }
    (JOB_DIR / "visual_project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    (JOB_DIR / "publish.json").write_text(json.dumps(publish, ensure_ascii=False, indent=2), encoding="utf-8")
    (JOB_DIR / "render_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if not SCREENSHOT.exists():
        raise FileNotFoundError(f"Missing webpage screenshot: {SCREENSHOT}")
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    if RENDER_DIR.exists():
        shutil.rmtree(RENDER_DIR)
    audio, duration = build_audio()
    silent = render_video_stream(duration)
    final = mux_audio(silent, audio)
    write_metadata(final, duration)
    print(final.resolve())


if __name__ == "__main__":
    main()
