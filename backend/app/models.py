from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Motion = Literal["push_in", "slow_zoom", "pan_left", "pan_up", "still"]
Tone = Literal["cinematic", "documentary", "warm", "sharp", "minimal"]


class UploadedAsset(BaseModel):
    filename: str
    url: str
    path: str
    width: int
    height: int


class Shot(BaseModel):
    id: str
    image_index: int = Field(0, ge=0)
    title: str = Field(..., min_length=1)
    caption: str = Field(..., min_length=1)
    duration: float = Field(3.5, ge=1.5, le=8.0)
    motion: Motion = "slow_zoom"
    emphasis: str = ""


class VideoPlan(BaseModel):
    title: str = Field(..., min_length=1)
    hook: str = Field(..., min_length=1)
    tone: Tone = "documentary"
    aspect_ratio: str = "9:16"
    duration_seconds: float = Field(24.0, ge=8.0, le=60.0)
    music_query: str = ""
    weishi_caption: str = ""
    hashtags: List[str] = Field(default_factory=list)
    shots: List[Shot] = Field(default_factory=list)


class PlanResponse(BaseModel):
    job_id: str
    images: List[UploadedAsset]
    plan: VideoPlan
    used_llm: bool = False
    warning: Optional[str] = None


class MusicSearchRequest(BaseModel):
    query: str = ""
    mood: str = "warm"
    duration_seconds: float = 24.0


class MusicCandidate(BaseModel):
    id: str
    title: str
    source: str
    prompt: str
    status: str
    path: Optional[str] = None
    url: Optional[str] = None
    can_download: bool = False
    note: str = ""


class MusicGenerateRequest(BaseModel):
    job_id: str
    prompt: str
    duration_seconds: float = 24.0
    seamless: bool = True


class RenderRequest(BaseModel):
    job_id: str
    plan: VideoPlan
    music_path: Optional[str] = None
    use_sak_music: bool = False


class RenderResponse(BaseModel):
    job_id: str
    video_url: str
    video_path: str
    music_warning: Optional[str] = None


class VideoRecord(BaseModel):
    job_id: str
    filename: str
    video_url: str
    video_path: str
    title: str = ""
    caption: str = ""
    short_title: str = ""
    video_description: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    size_bytes: int = 0
    created_at: str = ""
    publish_status: str = "draft"
    publish_channel: str = "weishi"
    publish_note: str = ""
    published_at: str = ""


class PublishVideoRequest(BaseModel):
    job_id: str
    filename: str
    channel: str = "weishi"
    caption: str = ""
    short_title: str = ""
    video_description: str = ""


class PublishVideoResponse(BaseModel):
    ok: bool
    record: VideoRecord
    short_title: str
    video_description: str
    publish_text: str
    message: str


class SettingsResponse(BaseModel):
    env_path: str
    values: Dict[str, str]
    restart_required_keys: List[str]


class SettingsSaveRequest(BaseModel):
    values: Dict[str, str]


class MusicPromptRequest(BaseModel):
    plan: VideoPlan
    caption: str = ""
    mood: str = "warm"
