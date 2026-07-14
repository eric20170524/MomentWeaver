from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .env_config import ENV_PATH, RESTART_REQUIRED_KEYS, effective_settings, load_env_file_into_process, save_settings
from .llm_planner import NebulaStoryboardPlanner
from .models import (
    MusicGenerateRequest,
    MusicPromptRequest,
    MusicSearchRequest,
    PlanResponse,
    PublishVideoRequest,
    PublishVideoResponse,
    RenderRequest,
    RenderResponse,
    SettingsResponse,
    SettingsSaveRequest,
    UploadedAsset,
    VideoRecord,
    VisualRenderRequest,
    VisualRenderResponse,
    VisualRenderStatus,
)
from .music_assets import MusicAssetService
from .settings import DOCS_EXAMPLES_DIR, FRONTEND_DIR, JOBS_DIR, LEGACY_FRONTEND_DIR, ensure_storage, job_dir
from .video_renderer import render_video
from .visual_renderer import render_visual_project, visual_project_to_plan_dict


app = FastAPI(title="MomentWeaver", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

planner = NebulaStoryboardPlanner()
music_service = MusicAssetService()


@app.on_event("startup")
async def startup() -> None:
    load_env_file_into_process()
    ensure_storage()


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
app.mount("/legacy-static", StaticFiles(directory=str(LEGACY_FRONTEND_DIR)), name="legacy-static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/legacy")
@app.get("/legacy/")
async def legacy_index() -> HTMLResponse:
    html = (LEGACY_FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace('"/static/', '"/legacy-static/')
    return HTMLResponse(html)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "app": "MomentWeaver"}


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    return SettingsResponse(
        env_path=str(ENV_PATH),
        values=effective_settings(),
        restart_required_keys=sorted(RESTART_REQUIRED_KEYS),
    )


@app.post("/api/settings", response_model=SettingsResponse)
async def update_settings(request: SettingsSaveRequest) -> SettingsResponse:
    values = save_settings(request.values)
    return SettingsResponse(
        env_path=str(ENV_PATH),
        values=values,
        restart_required_keys=sorted(RESTART_REQUIRED_KEYS),
    )


@app.get("/api/examples")
async def examples() -> dict:
    if not DOCS_EXAMPLES_DIR.exists():
        return {"examples": []}
    items = []
    for path in sorted(DOCS_EXAMPLES_DIR.glob("*.png")):
        items.append({"filename": path.name, "url": f"/api/examples/{path.name}"})
    return {"examples": items}


@app.get("/api/examples/{filename}")
async def example_image(filename: str) -> FileResponse:
    path = DOCS_EXAMPLES_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Example not found")
    return FileResponse(path)


def _safe_ext(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower()
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "webp" in content_type:
        return ".webp"
    return ".png"


async def _save_upload(job_id: str, index: int, upload: UploadFile) -> UploadedAsset:
    if not (upload.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail=f"{upload.filename} is not an image")
    source_dir = job_dir(job_id) / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    ext = _safe_ext(upload)
    filename = f"image_{index:02d}{ext}"
    path = source_dir / filename
    with path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)

    try:
        with Image.open(path) as image:
            width, height = image.size
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid image: {upload.filename}") from exc

    return UploadedAsset(
        filename=upload.filename or filename,
        url=f"/api/jobs/{job_id}/image/{filename}",
        path=str(path.resolve()),
        width=width,
        height=height,
    )


def _job_images(job_id: str) -> List[UploadedAsset]:
    source_dir = job_dir(job_id) / "source"
    if not source_dir.exists():
        return []
    assets: List[UploadedAsset] = []
    for index, path in enumerate(sorted(source_dir.glob("image_*"))):
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception:
            continue
        assets.append(
            UploadedAsset(
                filename=path.name,
                url=f"/api/jobs/{job_id}/image/{path.name}",
                path=str(path.resolve()),
                width=width,
                height=height,
            )
        )
    return assets


def _safe_job_id(job_id: str) -> str:
    safe = Path(job_id).name
    if not safe or safe != job_id:
        raise HTTPException(status_code=400, detail="Invalid job id")
    return safe


def _safe_filename(filename: str) -> str:
    safe = Path(filename).name
    if not safe or safe != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return safe


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _iso_timestamp(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


def _probe_video(path: Path) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if result.returncode != 0:
        return {}
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    stream = streams[0] if streams else {}
    duration = stream.get("duration")
    return {
        "width": stream.get("width"),
        "height": stream.get("height"),
        "duration_seconds": round(float(duration), 2) if duration else None,
    }


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u2028", "\n").split()).strip()


def _clip_text(value: str, limit: int) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip("，。,. ") + "…"


def _short_title_score(text: str, source: str) -> int:
    score = 0
    length = len(text)
    if 6 <= length <= 14:
        score += 14
    elif 15 <= length <= 20:
        score += 8
    elif 3 <= length < 6:
        score += 4
    else:
        score -= 8

    if source == "shot_title":
        score += 8
    elif source == "shot_caption":
        score += 3
    elif source == "explicit":
        score += 6
    elif source == "plan_title":
        score -= 8
    elif source == "fallback":
        score -= 12

    friendly_terms = {
        "普通人": 14,
        "也能": 12,
        "你": 6,
        "我": 4,
        "我们": 5,
        "一起": 5,
        "开始": 5,
        "做作品": 10,
        "小白": 8,
        "新手": 8,
        "如何": 6,
        "怎么": 6,
        "别再": 5,
        "多学": 5,
        "少躺": 5,
        "自主": 4,
    }
    for term, weight in friendly_terms.items():
        if term in text:
            score += weight

    formal_terms = {
        "时代": 6,
        "趋势": 5,
        "已经到来": 10,
        "正式进入": 8,
        "浪潮": 5,
        "百年难遇": 6,
        "何其": 4,
        "珍贵": 3,
    }
    for term, penalty in formal_terms.items():
        if term in text:
            score -= penalty

    return score


def _generated_short_title(plan: Dict[str, Any], demo: Dict[str, Any], fallback: str) -> str:
    candidates: List[tuple[str, str]] = []
    for value in [plan.get("short_title"), demo.get("short_title")]:
        text = _clean_text(value)
        if text:
            candidates.append((text, "explicit"))

    for shot in plan.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for key, source in [("title", "shot_title"), ("caption", "shot_caption")]:
            text = _clean_text(shot.get(key))
            if text:
                candidates.append((text, source))

    for value, source in [
        (plan.get("hook"), "hook"),
        (plan.get("title"), "plan_title"),
        (demo.get("title"), "plan_title"),
        (fallback, "fallback"),
    ]:
        text = _clean_text(value)
        if text:
            candidates.append((text, source))

    best = ""
    best_score = -10_000
    seen: set[str] = set()
    for candidate, source in candidates:
        text = _clip_text(candidate, 20)
        if not text or text in seen:
            continue
        seen.add(text)
        score = _short_title_score(text, source)
        if score > best_score:
            best = text
            best_score = score

    return best or "朋友圈短视频"


def _generated_video_description(plan: Dict[str, Any], demo: Dict[str, Any], title: str) -> str:
    candidates = [
        plan.get("video_description"),
        demo.get("video_description"),
        plan.get("weishi_caption"),
        demo.get("weishi_caption"),
    ]
    for candidate in candidates:
        text = _clean_text(candidate)
        if text:
            return _clip_text(text, 480)

    hook = _clean_text(plan.get("hook") or title)
    hashtags = plan.get("hashtags") or []
    tag_text = " ".join(f"#{_clean_text(tag)}" for tag in hashtags[:4] if _clean_text(tag))
    description = f"{hook} {tag_text}".strip()
    return _clip_text(description or title, 480)


def _publish_store_path(job_path: Path) -> Path:
    return job_path / "publish.json"


def _load_publish_states(job_path: Path) -> Dict[str, Dict[str, str]]:
    data = _read_json(_publish_store_path(job_path))
    states = data.get("videos") if isinstance(data, dict) else {}
    return states if isinstance(states, dict) else {}


def _save_publish_state(job_path: Path, filename: str, state: Dict[str, str]) -> None:
    states = _load_publish_states(job_path)
    states[filename] = state
    _publish_store_path(job_path).write_text(
        json.dumps({"videos": states}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_status_path(job_path: Path) -> Path:
    return job_path / "render_status.json"


def _write_render_status(
    job_path: Path,
    *,
    status: str,
    project_path: Path,
    video_path: Optional[Path] = None,
    error: Optional[str] = None,
) -> Dict[str, str]:
    data = {
        "job_id": job_path.name,
        "status": status,
        "project_path": str(project_path.resolve()),
        "status_path": str(_render_status_path(job_path).resolve()),
        "video_url": f"/api/jobs/{quote(job_path.name)}/video/{quote(video_path.name)}" if video_path else "",
        "video_path": str(video_path.resolve()) if video_path else "",
        "error": error or "",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _render_status_path(job_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _video_record(job_path: Path, video_path: Path) -> VideoRecord:
    job_id = job_path.name
    plan = _read_json(job_path / "plan.json")
    demo = _read_json(job_path / "demo_result.json")
    states = _load_publish_states(job_path)
    publish_state = states.get(video_path.name, {})
    probe = _probe_video(video_path)
    try:
        size_bytes = video_path.stat().st_size
    except OSError:
        size_bytes = 0

    caption = plan.get("weishi_caption") or demo.get("weishi_caption") or ""
    title = plan.get("title") or demo.get("title") or job_id
    short_title = publish_state.get("short_title") or _generated_short_title(plan, demo, title)
    video_description = publish_state.get("video_description") or publish_state.get("caption") or _generated_video_description(plan, demo, title)
    return VideoRecord(
        job_id=job_id,
        filename=video_path.name,
        video_url=f"/api/jobs/{quote(job_id)}/video/{quote(video_path.name)}",
        video_path=str(video_path.resolve()),
        title=title,
        caption=caption,
        short_title=short_title,
        video_description=video_description,
        width=probe.get("width"),
        height=probe.get("height"),
        duration_seconds=probe.get("duration_seconds"),
        size_bytes=size_bytes,
        created_at=_iso_timestamp(video_path),
        publish_status=publish_state.get("status", "draft"),
        publish_channel=publish_state.get("channel", "weishi"),
        publish_note=publish_state.get("note", ""),
        published_at=publish_state.get("published_at", ""),
    )


def _find_video_record(job_id: str, filename: str) -> VideoRecord:
    safe_job_id = _safe_job_id(job_id)
    safe_filename = _safe_filename(filename)
    job_path = job_dir(safe_job_id)
    video_path = job_path / "videos" / safe_filename
    if not video_path.exists() or video_path.suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail="Video not found")
    return _video_record(job_path, video_path)


@app.post("/api/analyze", response_model=PlanResponse)
async def analyze(
    caption: str = Form(""),
    tone: str = Form("documentary"),
    duration_seconds: float = Form(24.0),
    images: List[UploadFile] = File(default=[]),
) -> PlanResponse:
    if not caption.strip():
        raise HTTPException(status_code=400, detail="Caption is required")
    if len(images) > 12:
        raise HTTPException(status_code=400, detail="Please upload 12 images or fewer")

    job_id = uuid.uuid4().hex[:12]
    assets = []
    for index, upload in enumerate(images):
        assets.append(await _save_upload(job_id, index, upload))

    plan, used_llm, warning = await planner.create_plan(
        caption=caption,
        assets=assets,
        tone=tone,
        duration_seconds=duration_seconds,
    )
    return PlanResponse(job_id=job_id, images=assets, plan=plan, used_llm=used_llm, warning=warning)


@app.post("/api/music/search")
async def music_search(request: MusicSearchRequest) -> dict:
    return {"candidates": [item.dict() for item in await music_service.search(request)]}


@app.post("/api/music/prompt")
async def music_prompt(request: MusicPromptRequest) -> dict:
    prompt = music_service.prompt_from_plan(request.plan, caption=request.caption, mood=request.mood)
    return {"prompt": prompt}


@app.post("/api/music/generate")
async def music_generate(request: MusicGenerateRequest) -> dict:
    try:
        path, warning = await music_service.generate_with_sak(
            prompt=request.prompt,
            job_dir=job_dir(request.job_id),
            duration_seconds=request.duration_seconds,
            seamless=request.seamless,
        )
        return {"path": str(path.resolve()), "url": f"/api/jobs/{request.job_id}/music/{path.name}", "warning": warning}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/music/download")
async def music_download(request: MusicGenerateRequest) -> dict:
    return await music_generate(request)


@app.post("/api/render", response_model=RenderResponse)
async def render(request: RenderRequest) -> RenderResponse:
    images = _job_images(request.job_id)
    if not images:
        raise HTTPException(status_code=400, detail="No images found for this job")

    music_warning = None
    music_path = Path(request.music_path).resolve() if request.music_path else None
    if request.use_sak_music and not music_path:
        try:
            music_path, music_warning = await music_service.generate_with_sak(
                prompt=request.plan.music_query or "温暖轻电子短视频背景音乐",
                job_dir=job_dir(request.job_id),
                duration_seconds=request.plan.duration_seconds,
                seamless=True,
            )
        except Exception as exc:
            music_warning = f"SAK music generation skipped: {exc}"
            music_path = None

    try:
        video_path = render_video(
            job_id=request.job_id,
            plan=request.plan,
            images=images,
            output_dir=job_dir(request.job_id),
            music_path=music_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RenderResponse(
        job_id=request.job_id,
        video_url=f"/api/jobs/{request.job_id}/video/{video_path.name}",
        video_path=str(video_path.resolve()),
        music_warning=music_warning,
    )


@app.post("/api/visual-projects/render", response_model=VisualRenderResponse)
async def render_visual_project_endpoint(request: VisualRenderRequest) -> VisualRenderResponse:
    job_id = _safe_job_id(request.job_id) if request.job_id else f"visual_{uuid.uuid4().hex[:12]}"
    job_path = job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=True)
    project_path = job_path / "visual_project.json"
    publish_path = _publish_store_path(job_path)

    project_path.write_text(
        json.dumps(request.project.dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_render_status(job_path, status="rendering", project_path=project_path)

    try:
        video_path = render_visual_project(
            job_id=job_id,
            project=request.project,
            output_dir=job_path,
        )
    except Exception as exc:
        status_data = _write_render_status(job_path, status="failed", project_path=project_path, error=str(exc))
        raise HTTPException(status_code=500, detail=status_data) from exc

    plan_data = visual_project_to_plan_dict(request.project)
    (job_path / "plan.json").write_text(json.dumps(plan_data, ensure_ascii=False, indent=2), encoding="utf-8")

    short_title = _clip_text(request.project.title, 20)
    video_description = _clip_text(
        request.project.weishi_caption or request.project.description or request.project.title,
        480,
    )
    now = datetime.now().isoformat(timespec="seconds")
    _save_publish_state(
        job_path,
        video_path.name,
        {
            "status": "ready",
            "channel": "weishi",
            "note": "由 video-background-board 可视编辑结果提交 MomentWeaver 后端渲染，已准备手动发布。",
            "published_at": now,
            "short_title": short_title,
            "video_description": video_description,
            "caption": video_description,
        },
    )

    status_data = _write_render_status(job_path, status="rendered", project_path=project_path, video_path=video_path)
    publish_text = (
        f"短标题：{short_title}\n\n"
        f"视频描述：\n{video_description}\n\n"
        f"视频文件：{video_path.resolve()}"
    ).strip()
    return VisualRenderResponse(
        **status_data,
        publish_path=str(publish_path.resolve()),
        publish_text=publish_text,
        message="已完成后端 MP4 渲染并写入发布准备状态",
    )


@app.get("/api/visual-projects/{job_id}/status", response_model=VisualRenderStatus)
async def get_visual_project_status(job_id: str) -> VisualRenderStatus:
    safe_job_id = _safe_job_id(job_id)
    job_path = job_dir(safe_job_id)
    status_path = _render_status_path(job_path)
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="Render status not found")
    data = _read_json(status_path)
    if data.get("error") == "":
        data["error"] = None
    return VisualRenderStatus(**data)


@app.get("/api/videos")
async def list_videos(limit: int = 50) -> dict:
    ensure_storage()
    records: List[VideoRecord] = []
    for videos_dir in JOBS_DIR.glob("*/videos"):
        job_path = videos_dir.parent
        for video_path in videos_dir.glob("*.mp4"):
            records.append(_video_record(job_path, video_path))
    records.sort(key=lambda item: item.created_at, reverse=True)
    return {"videos": [item.dict() for item in records[: max(1, min(limit, 200))]]}


@app.post("/api/publish/weishi", response_model=PublishVideoResponse)
async def publish_weishi(request: PublishVideoRequest) -> PublishVideoResponse:
    if request.channel not in {"weishi", "wechat_weishi"}:
        raise HTTPException(status_code=400, detail="Unsupported publish channel")

    record = _find_video_record(request.job_id, request.filename)
    short_title = _clip_text(request.short_title or record.short_title, 20)
    video_description = _clip_text(request.video_description or request.caption or record.video_description or record.caption, 480)
    now = datetime.now().isoformat(timespec="seconds")
    state = {
        "status": "ready",
        "channel": "weishi",
        "note": "已准备发布到微信微视，请在微视发布页选择本地 MP4 并粘贴文案。",
        "published_at": now,
        "short_title": short_title,
        "video_description": video_description,
        "caption": video_description,
    }
    _save_publish_state(job_dir(record.job_id), record.filename, state)
    record = _find_video_record(record.job_id, record.filename)
    publish_text = (
        f"短标题：{short_title}\n\n"
        f"视频描述：\n{video_description}\n\n"
        f"视频文件：{record.video_path}"
    ).strip()
    return PublishVideoResponse(
        ok=True,
        record=record,
        short_title=short_title,
        video_description=video_description,
        publish_text=publish_text,
        message="已准备好微视发布信息",
    )


@app.get("/api/jobs/{job_id}/image/{filename}")
async def job_image(job_id: str, filename: str) -> FileResponse:
    path = job_dir(job_id) / "source" / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/music/{filename}")
async def job_music(job_id: str, filename: str) -> FileResponse:
    path = job_dir(job_id) / "music" / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Music not found")
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/video/{filename}")
async def job_video(job_id: str, filename: str) -> FileResponse:
    path = job_dir(job_id) / "videos" / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path, media_type="video/mp4", filename=path.name)
