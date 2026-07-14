from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Iterable, List, Optional

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageOps

from .models import VisualCanvasElement, VisualProject
from .video_renderer import RESAMPLE, _draw_multiline, _font, _quote_ffconcat, _run_ffmpeg, _text_width, _wrap_text


def _rgb(value: str | None, fallback: tuple[int, int, int] = (15, 23, 42)) -> tuple[int, int, int]:
    text = (value or "").strip()
    if text.startswith("rgba"):
        try:
            parts = text[text.index("(") + 1 : text.rindex(")")].split(",")
            return tuple(max(0, min(255, int(float(part.strip())))) for part in parts[:3])  # type: ignore[return-value]
        except (ValueError, IndexError):
            return fallback
    try:
        color = ImageColor.getrgb(text)
        return color[:3] if isinstance(color, tuple) else fallback
    except ValueError:
        return fallback


def _rgba(value: str | None, opacity: float = 1) -> tuple[int, int, int, int]:
    r, g, b = _rgb(value)
    return (r, g, b, max(0, min(255, int(255 * opacity))))


def _blend(start: tuple[int, int, int], end: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(start[index] + (end[index] - start[index]) * t) for index in range(3))  # type: ignore[return-value]


def _background(project: VisualProject) -> Image.Image:
    size = (project.canvas.width, project.canvas.height)
    config = project.background
    if config.type == "solid":
        image = Image.new("RGBA", size, (*_rgb(config.solidColor), 255))
    else:
        colors = [_rgb(color) for color in config.gradientColors if color]
        if len(colors) < 2:
            colors = [_rgb(config.solidColor), (30, 27, 75)]
        image = Image.new("RGBA", size)
        draw = ImageDraw.Draw(image)
        height = max(1, size[1] - 1)
        segments = len(colors) - 1
        for y in range(size[1]):
            position = (y / height) * segments
            index = min(segments - 1, int(position))
            local_t = position - index
            draw.line([(0, y), (size[0], y)], fill=(*_blend(colors[index], colors[index + 1], local_t), 255))

    _draw_embellishments(image, project)
    if config.type == "glassmorphism":
        overlay = Image.new("RGBA", size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        margin_x = int(size[0] * 0.04)
        margin_y = int(size[1] * 0.05)
        draw.rounded_rectangle(
            (margin_x, margin_y, size[0] - margin_x, size[1] - margin_y),
            radius=max(18, int(min(size) * 0.03)),
            fill=(255, 255, 255, int(255 * config.glassOpacity)),
            outline=(255, 255, 255, int(255 * config.glassBorderOpacity)),
            width=3,
        )
        image = Image.alpha_composite(image, overlay)
    if config.showGrid:
        draw = ImageDraw.Draw(image)
        grid_color = _rgba(config.gridColor, 0.55)
        step_x = max(80, size[0] // 12)
        step_y = max(80, size[1] // 8)
        for x in range(0, size[0], step_x):
            draw.line([(x, 0), (x, size[1])], fill=grid_color, width=1)
        for y in range(0, size[1], step_y):
            draw.line([(0, y), (size[0], y)], fill=grid_color, width=1)
    return image


def _draw_embellishments(image: Image.Image, project: VisualProject) -> None:
    for item in project.background.embellishments:
        size = max(8, int(item.size))
        x = int(project.canvas.width * item.x / 100)
        y = int(project.canvas.height * item.y / 100)
        layer = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(layer)
        fill = _rgba(item.color, item.opacity)
        if item.type in {"circle", "ring", "mesh-blob"}:
            if item.type == "ring":
                draw.ellipse((4, 4, size - 4, size - 4), outline=fill, width=max(2, size // 24))
            else:
                draw.ellipse((0, 0, size, size), fill=fill)
        elif item.type == "square":
            draw.rounded_rectangle((0, 0, size, size), radius=max(2, size // 10), fill=fill)
        else:
            points = [
                (size * 0.5, 0),
                (size * 0.62, size * 0.36),
                (size, size * 0.38),
                (size * 0.69, size * 0.6),
                (size * 0.8, size),
                (size * 0.5, size * 0.76),
                (size * 0.2, size),
                (size * 0.31, size * 0.6),
                (0, size * 0.38),
                (size * 0.38, size * 0.36),
            ]
            draw.polygon(points, fill=fill)
        if item.blur > 0:
            layer = layer.filter(ImageFilter.GaussianBlur(radius=max(0, float(item.blur) / 3)))
        image.alpha_composite(layer, (x - size // 2, y - size // 2))


def _image_from_data_url(src: str) -> Optional[Image.Image]:
    if src.startswith("data:") and "," in src:
        try:
            payload = src.split(",", 1)[1]
            return ImageOps.exif_transpose(Image.open(BytesIO(base64.b64decode(payload)))).convert("RGBA")
        except Exception:
            return None

    # Try local image loading fallback
    try:
        from .settings import DOCS_EXAMPLES_DIR, JOBS_DIR
        import urllib.parse

        path = urllib.parse.unquote(src)
        if "/api/examples/" in path:
            filename = path.split("/api/examples/")[-1]
            filepath = DOCS_EXAMPLES_DIR / filename
            if filepath.exists():
                return ImageOps.exif_transpose(Image.open(filepath)).convert("RGBA")
        elif "/api/jobs/" in path:
            parts = path.split("/api/jobs/")[-1].split("/")
            if len(parts) >= 3:
                jid = parts[0]
                filename = parts[-1]
                filepath = JOBS_DIR / jid / "source" / filename
                if filepath.exists():
                    return ImageOps.exif_transpose(Image.open(filepath)).convert("RGBA")
    except Exception:
        pass

    return None


def _apply_opacity(layer: Image.Image, opacity: float) -> Image.Image:
    layer = layer.convert("RGBA")
    if opacity >= 0.999:
        return layer
    alpha = layer.getchannel("A")
    alpha = alpha.point(lambda value: max(0, min(255, int(value * opacity))))
    layer.putalpha(alpha)
    return layer


def _scale_rotate(layer: Image.Image, scale: float, rotation: float) -> Image.Image:
    if abs(scale - 1) > 0.01:
        width = max(1, int(layer.width * scale))
        height = max(1, int(layer.height * scale))
        layer = layer.resize((width, height), RESAMPLE)
    if abs(rotation) > 0.01:
        layer = layer.rotate(-rotation, expand=True, resample=RESAMPLE)
    return layer


def _render_text_layer(element: VisualCanvasElement, canvas_size: tuple[int, int]) -> Optional[Image.Image]:
    text = (element.textContent or element.voiceoverText or "").strip()
    if not text:
        return None
    font_size = max(8, int(element.fontSize or 48))
    font = _font(font_size)
    max_width = max(240, min(int(canvas_size[0] * 0.72), 1200))
    scratch = Image.new("RGBA", (max_width + 120, max(240, int(font_size * 9))), (255, 255, 255, 0))
    draw = ImageDraw.Draw(scratch)
    lines = _wrap_text(draw, text, font, max_width, 7)
    y = 48
    for line in lines:
        line_width = _text_width(draw, line, font)
        if element.textAlign == "left":
            x = 48
        elif element.textAlign == "right":
            x = 48 + max_width - line_width
        else:
            x = 48 + max(0, (max_width - line_width) // 2)
        _draw_multiline(
            draw,
            (x, y),
            [line],
            font,
            element.color or "#ffffff",
            max(8, font_size // 5),
            stroke_width=2 if element.textShadow != "none" else 0,
            stroke_fill="#000000",
        )
        y += int(font_size * 1.35)
    bbox = scratch.getbbox()
    if not bbox:
        return None
    return scratch.crop(bbox)


def _render_image_layer(element: VisualCanvasElement) -> Optional[Image.Image]:
    if not element.imageSrc:
        return None
    source = _image_from_data_url(element.imageSrc)
    if source is None:
        return None
    target_w = int(element.width or min(420, source.width))
    target_h = int(element.height or min(420, source.height))
    source.thumbnail((max(1, target_w), max(1, target_h)), RESAMPLE)
    layer = Image.new("RGBA", (max(1, target_w), max(1, target_h)), (255, 255, 255, 0))
    layer.alpha_composite(source, ((layer.width - source.width) // 2, (layer.height - source.height) // 2))
    return layer


def _render_decoration_layer(element: VisualCanvasElement) -> Image.Image:
    icon_map = {
        "sparkle": "✨",
        "abstract-blob": "◆",
        "badge": "★",
        "heart": "♥",
        "star": "★",
        "glow-light": "●",
    }
    icon = icon_map.get(element.decorationType or "", "★")
    layer = Image.new("RGBA", (180, 180), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(110)
    color = element.color or "#ffffff"
    if element.decorationType == "glow-light":
        draw.ellipse((34, 34, 146, 146), fill=(59, 130, 246, 150))
        return layer.filter(ImageFilter.GaussianBlur(14))
    _draw_multiline(draw, (35, 22), [icon], font, color, 0, stroke_width=2, stroke_fill="#000000")
    return layer


def _render_widget_layer(element: VisualCanvasElement, time_seconds: float) -> Image.Image:
    layer = Image.new("RGBA", (360, 150), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, 360, 150), radius=28, fill=(12, 18, 32, 210), outline=(255, 255, 255, 40), width=2)
    label = (element.widgetType or "widget").replace("-", " ").upper()
    draw.text((28, 26), label, font=_font(22), fill="#94a3b8")
    if element.widgetType == "audio-wave":
        for index, height in enumerate([28, 58, 42, 78, 48, 88, 40, 64, 35, 70]):
            x = 32 + index * 28
            draw.rounded_rectangle((x, 118 - height, x + 12, 118), radius=6, fill="#38bdf8")
    else:
        draw.text((28, 64), f"{time_seconds:05.1f}s", font=_font(52), fill="#f8fafc")
    return layer


def _element_timeline(element: VisualCanvasElement, time_seconds: float) -> tuple[bool, float, float, float]:
    if time_seconds < element.startTime or time_seconds > element.endTime:
        return False, 0, element.scale, 0

    opacity = element.opacity
    scale = element.scale
    offset_y = 0.0
    elapsed = time_seconds - element.startTime
    remaining = element.endTime - time_seconds

    if element.fadeInDuration > 0 and elapsed < element.fadeInDuration:
        progress = max(0.0, min(1.0, elapsed / element.fadeInDuration))
        opacity *= progress
        if element.animationType == "zoom":
            scale *= 0.6 + 0.4 * progress
        elif element.animationType == "slide-up":
            offset_y = 48 * (1 - progress)

    if element.fadeOutDuration > 0 and remaining < element.fadeOutDuration:
        progress = max(0.0, min(1.0, remaining / element.fadeOutDuration))
        opacity *= progress
        if element.animationType == "zoom":
            scale *= 0.6 + 0.4 * progress
        elif element.animationType == "slide-up":
            offset_y = 48 * (1 - progress)

    return True, opacity, scale, offset_y


def render_visual_frame(project: VisualProject, time_seconds: float, out_path: Path) -> None:
    canvas = _background(project)
    canvas_size = (project.canvas.width, project.canvas.height)
    for element in sorted(project.elements, key=lambda item: item.zIndex):
        is_visible, opacity, scale, offset_y = _element_timeline(element, time_seconds)
        if not is_visible or opacity <= 0:
            continue
        if element.type == "text":
            layer = _render_text_layer(element, canvas_size)
        elif element.type == "image":
            layer = _render_image_layer(element)
        elif element.type == "decoration":
            layer = _render_decoration_layer(element)
        else:
            layer = _render_widget_layer(element, time_seconds)
        if layer is None:
            continue
        layer = _scale_rotate(layer, scale, element.rotation)
        layer = _apply_opacity(layer, opacity)
        x = int(project.canvas.width * element.x / 100 - layer.width / 2)
        y = int(project.canvas.height * element.y / 100 - layer.height / 2 + offset_y)
        canvas.alpha_composite(layer, (x, y))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, quality=94)


def _timeline_breakpoints(project: VisualProject) -> List[float]:
    duration = float(project.timelineDuration)
    values = {0.0, duration}
    for element in project.elements:
        start = max(0.0, min(duration, float(element.startTime)))
        end = max(0.0, min(duration, float(element.endTime)))
        if end <= start:
            continue
        values.update({start, end})
        values.add(min(duration, start + max(0.0, float(element.fadeInDuration))))
        values.add(max(0.0, end - max(0.0, float(element.fadeOutDuration))))
    ordered = sorted(value for value in values if 0 <= value <= duration)
    return ordered if len(ordered) >= 2 else [0.0, duration]


def render_visual_project(job_id: str, project: VisualProject, output_dir: Path) -> Path:
    render_dir = output_dir / "visual_render"
    frames_dir = render_dir / "frames"
    videos_dir = output_dir / "videos"
    frames_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    breakpoints = _timeline_breakpoints(project)
    frame_paths: List[Path] = []
    durations: List[float] = []
    for index, (start, end) in enumerate(zip(breakpoints, breakpoints[1:])):
        duration = max(0.05, end - start)
        if duration < 0.05:
            continue
        frame_path = frames_dir / f"visual_frame_{index:03d}.jpg"
        render_visual_frame(project, start + duration / 2, frame_path)
        frame_paths.append(frame_path)
        durations.append(duration)

    if not frame_paths:
        frame_path = frames_dir / "visual_frame_000.jpg"
        render_visual_frame(project, 0, frame_path)
        frame_paths.append(frame_path)
        durations.append(max(1.0, float(project.timelineDuration)))

    concat_path = render_dir / "visual_slides.ffconcat"
    with concat_path.open("w", encoding="utf-8") as handle:
        handle.write("ffconcat version 1.0\n")
        for frame_path, duration in zip(frame_paths, durations):
            handle.write(_quote_ffconcat(frame_path))
            handle.write(f"duration {duration:.3f}\n")
        handle.write(_quote_ffconcat(frame_paths[-1]))

    silent_video = render_dir / "visual_video_no_audio.mp4"
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

    final_video = videos_dir / f"{job_id}_visual.mp4"

    # Check for background music in the job folder
    music_path = None
    for ext in ["mp3", "wav"]:
        p = output_dir / "music" / f"bgm.{ext}"
        if p.exists():
            music_path = p
            break

    if music_path:
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


def _visible_texts(project: VisualProject, start: float, end: float) -> Iterable[str]:
    for element in sorted(project.elements, key=lambda item: (item.startTime, item.zIndex)):
        if element.endTime <= start or element.startTime >= end:
            continue
        if element.type == "text" and element.textContent:
            yield element.textContent.strip()
        if element.voiceoverText:
            yield element.voiceoverText.strip()
        for segment in element.audioSegments:
            if segment.endTime > start and segment.startTime < end and segment.text:
                yield segment.text.strip()


def visual_project_to_plan_dict(project: VisualProject) -> dict:
    breakpoints = _timeline_breakpoints(project)
    shots = []
    for index, (start, end) in enumerate(zip(breakpoints, breakpoints[1:])):
        texts = [text for text in _visible_texts(project, start, end) if text]
        title = texts[0] if texts else project.title
        caption = " ".join(texts[:2]) if texts else project.description or project.weishi_caption or project.title
        shots.append(
            {
                "id": f"visual-shot-{index + 1}",
                "image_index": 0,
                "title": title[:80],
                "caption": caption[:180],
                "duration": round(max(0.05, end - start), 3),
                "motion": "still",
                "emphasis": "来自 video-background-board 时间轴与舞台编辑结果",
            }
        )

    clean_tags = [tag.strip().lstrip("#") for tag in project.hashtags if tag.strip()]
    return {
        "title": project.title,
        "hook": project.description or project.title,
        "tone": "documentary",
        "aspect_ratio": project.canvas.aspect_ratio,
        "duration_seconds": project.timelineDuration,
        "music_query": "",
        "weishi_caption": project.weishi_caption or project.description or project.title,
        "hashtags": clean_tags[:8],
        "shots": shots,
        "source": project.source,
        "visual_contract": "VisualProject/v1",
    }
