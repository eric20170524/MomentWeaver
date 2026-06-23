from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .models import UploadedAsset, VideoPlan


CANVAS = (1080, 1920)
RESAMPLE = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]

EMOJI_FONT_CANDIDATES = [
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/System/Library/Fonts/Supplemental/Apple Color Emoji.ttc",
]

EMOJI_FONT_SIZES = (160, 128, 109, 96, 64, 48, 32, 24, 20, 16)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


@lru_cache(maxsize=32)
def _emoji_font(size: int) -> ImageFont.FreeTypeFont | None:
    candidate_sizes = sorted({size, *EMOJI_FONT_SIZES}, key=lambda value: abs(value - size))
    for path in EMOJI_FONT_CANDIDATES:
        if not Path(path).exists():
            continue
        for candidate_size in candidate_sizes:
            try:
                return ImageFont.truetype(path, size=candidate_size)
            except OSError:
                continue
    return None


def _is_emoji_char(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x1F000 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
        or codepoint in {0x200D, 0xFE0E, 0xFE0F}
    )


def _font_size(font: ImageFont.ImageFont) -> int:
    return int(getattr(font, "size", 32))


def _text_runs(text: str, font: ImageFont.ImageFont) -> list[tuple[str, ImageFont.ImageFont, bool]]:
    runs: list[tuple[str, ImageFont.ImageFont, bool]] = []
    current = ""
    current_font = font
    current_is_emoji = False

    for char in text:
        emoji_font = _emoji_font(_font_size(font)) if _is_emoji_char(char) else None
        run_font = emoji_font or font
        is_emoji = emoji_font is not None
        if current and (run_font != current_font or is_emoji != current_is_emoji):
            runs.append((current, current_font, current_is_emoji))
            current = ""
        current += char
        current_font = run_font
        current_is_emoji = is_emoji

    if current:
        runs.append((current, current_font, current_is_emoji))
    return runs


def _text_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    stroke_width: int = 0,
) -> tuple[int, int, int, int]:
    if not text:
        return (0, 0, 0, 0)

    x = 0
    top = 0
    bottom = 0
    for segment, segment_font, is_emoji in _text_runs(text, font):
        kwargs = {"font": segment_font}
        if is_emoji:
            kwargs["embedded_color"] = True
        else:
            kwargs["stroke_width"] = stroke_width
        box = draw.textbbox((0, 0), segment, **kwargs)
        width = box[2] - box[0]
        x += width
        top = min(top, box[1])
        bottom = max(bottom, box[3])
    return (0, top, x, bottom)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = _text_bbox(draw, text, font)
    return box[2] - box[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> List[str]:
    lines: List[str] = []
    current = ""
    for char in text.strip():
        if char == "\n":
            if current:
                lines.append(current)
            current = ""
            continue
        candidate = current + char
        if not current or _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = char
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len("".join(lines)) < len(text.strip()):
        lines[-1] = lines[-1].rstrip("，。,. ") + "..."
    return lines


def _fit_image(path: Path, max_size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(max_size, RESAMPLE)
    return image


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def _draw_multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    lines: List[str],
    font: ImageFont.ImageFont,
    fill: str,
    line_gap: int,
    stroke_width: int = 0,
    stroke_fill: str = "#000000",
) -> int:
    x, y = xy
    for line in lines:
        cursor_x = x
        for segment, segment_font, is_emoji in _text_runs(line, font):
            if is_emoji:
                draw.text((cursor_x, y), segment, font=segment_font, embedded_color=True)
            else:
                draw.text(
                    (cursor_x, y),
                    segment,
                    font=segment_font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_fill,
                )
            segment_box = _text_bbox(draw, segment, segment_font, stroke_width)
            cursor_x += segment_box[2] - segment_box[0]
        box = _text_bbox(draw, line, font, stroke_width)
        y += box[3] - box[1] + line_gap
    return y


def render_shot_frame(
    image_path: Optional[Path],
    plan: VideoPlan,
    shot_index: int,
    out_path: Path,
) -> None:
    shot = plan.shots[shot_index]
    if image_path and image_path.exists():
        source = Image.open(image_path).convert("RGB")
        background = ImageOps.fit(source, CANVAS, method=RESAMPLE)
        background = background.filter(ImageFilter.GaussianBlur(28))
    else:
        background = Image.new("RGB", CANVAS, "#16201d")

    dim = Image.new("RGBA", CANVAS, (0, 0, 0, 94))
    canvas = Image.alpha_composite(background.convert("RGBA"), dim)
    draw = ImageDraw.Draw(canvas)

    accent = "#35c2a1"
    coral = "#ff7a59"
    cream = "#fff8ef"
    ink = "#111816"

    draw.rounded_rectangle((72, 74, 448, 144), radius=35, fill=(255, 255, 255, 226))
    draw.ellipse((96, 94, 124, 122), fill=accent)
    draw.text((144, 89), "圈影 · 微视竖屏", font=_font(34), fill=ink)

    if image_path and image_path.exists():
        foreground = _fit_image(image_path, (900, 760))
        shadow_box = (
            (CANVAS[0] - foreground.width) // 2 + 10,
            256 + 12,
            (CANVAS[0] + foreground.width) // 2 + 10,
            256 + foreground.height + 12,
        )
        draw.rounded_rectangle(shadow_box, radius=28, fill=(0, 0, 0, 90))
        x = (CANVAS[0] - foreground.width) // 2
        y = 256
        mask = _rounded_mask(foreground.size, 28)
        canvas.paste(foreground.convert("RGBA"), (x, y), mask)
        draw.rounded_rectangle((x, y, x + foreground.width, y + foreground.height), radius=28, outline=(255, 255, 255, 160), width=3)

    text_panel_top = 1080
    draw.rounded_rectangle((72, text_panel_top, 1008, 1716), radius=34, fill=(255, 248, 239, 236))
    draw.rectangle((72, text_panel_top, 88, 1716), fill=coral)
    draw.text((118, text_panel_top + 62), f"{shot_index + 1:02d}", font=_font(42), fill=coral)

    title_font = _font(60)
    caption_font = _font(43)
    small_font = _font(30)
    title_lines = _wrap_text(draw, shot.title, title_font, 790, 2)
    y = _draw_multiline(draw, (190, text_panel_top + 44), title_lines, title_font, ink, 12)
    caption_lines = _wrap_text(draw, shot.caption, caption_font, 810, 4)
    _draw_multiline(draw, (118, y + 46), caption_lines, caption_font, "#1c2622", 18)

    emphasis = shot.emphasis or plan.hook
    emphasis_lines = _wrap_text(draw, emphasis, small_font, 810, 2)
    draw.rounded_rectangle((118, 1584, 962, 1666), radius=22, fill=(232, 247, 242, 255))
    _draw_multiline(draw, (146, 1607), emphasis_lines, small_font, "#245e51", 8)

    footer_font = _font(32)
    hashtags = " ".join(f"#{tag}" for tag in plan.hashtags[:3]) or "#朋友圈 #微视"
    draw.text((82, 1818), hashtags, font=footer_font, fill=cream, stroke_width=2, stroke_fill="#000000")
    draw.text((790, 1818), "MomentWeaver", font=footer_font, fill=cream, stroke_width=2, stroke_fill="#000000")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, quality=95)


def _quote_ffconcat(path: Path) -> str:
    escaped = str(path.resolve()).replace("\\", "\\\\").replace("'", "\\'")
    return f"file '{escaped}'\n"


def _run_ffmpeg(cmd: List[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "ffmpeg failed").strip()
        raise RuntimeError(detail[-2000:])


def render_video(
    job_id: str,
    plan: VideoPlan,
    images: List[UploadedAsset],
    output_dir: Path,
    music_path: Optional[Path] = None,
) -> Path:
    if not plan.shots:
        raise ValueError("Plan has no shots.")

    render_dir = output_dir / "render"
    frames_dir = render_dir / "frames"
    videos_dir = output_dir / "videos"
    frames_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: List[Path] = []
    for index, shot in enumerate(plan.shots):
        asset = images[shot.image_index % max(1, len(images))] if images else None
        image_path = Path(asset.path) if asset else None
        frame_path = frames_dir / f"frame_{index:03d}.jpg"
        render_shot_frame(image_path, plan, index, frame_path)
        frame_paths.append(frame_path)

    concat_path = render_dir / "slides.ffconcat"
    with concat_path.open("w", encoding="utf-8") as handle:
        handle.write("ffconcat version 1.0\n")
        for frame_path, shot in zip(frame_paths, plan.shots):
            handle.write(_quote_ffconcat(frame_path))
            handle.write(f"duration {float(shot.duration):.3f}\n")
        handle.write(_quote_ffconcat(frame_paths[-1]))

    silent_video = render_dir / "video_no_audio.mp4"
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vf",
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-movflags",
            "+faststart",
            str(silent_video),
        ]
    )

    final_video = videos_dir / f"{job_id}_weishi.mp4"
    if music_path and music_path.exists():
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(silent_video),
                "-stream_loop",
                "-1",
                "-i",
                str(music_path),
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-movflags",
                "+faststart",
                str(final_video),
            ]
        )
    else:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(silent_video),
                "-c:v",
                "copy",
                "-movflags",
                "+faststart",
                str(final_video),
            ]
        )
    return final_video
