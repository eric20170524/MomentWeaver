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


class VisualBackgroundEmbellishment(BaseModel):
    id: str
    type: str = "mesh-blob"
    color: str = "#3b82f6"
    x: float = 50
    y: float = 50
    size: float = 240
    blur: float = 80
    opacity: float = Field(0.4, ge=0, le=1)


class VisualBackgroundConfig(BaseModel):
    type: Literal["solid", "gradient", "glassmorphism"] = "solid"
    solidColor: str = "#0f172a"
    gradientAngle: float = 135
    gradientColors: List[str] = Field(default_factory=lambda: ["#0f172a", "#1e1b4b"])
    glassBlur: float = 16
    glassOpacity: float = Field(0.08, ge=0, le=1)
    glassBorderOpacity: float = Field(0.15, ge=0, le=1)
    showNoise: bool = False
    showGrid: bool = False
    gridColor: str = "rgba(255, 255, 255, 0.07)"
    embellishments: List[VisualBackgroundEmbellishment] = Field(default_factory=list)


class VisualCanvasSpec(BaseModel):
    width: int = Field(1920, ge=320, le=3840)
    height: int = Field(1080, ge=320, le=3840)
    aspect_ratio: str = "16:9"


class VisualAudioSegment(BaseModel):
    id: str
    startTime: float = Field(0, ge=0)
    endTime: float = Field(1, ge=0)
    text: str = ""
    voiceId: Optional[str] = None


class VisualCanvasElement(BaseModel):
    id: str
    type: Literal["text", "image", "decoration", "widget"]
    textContent: Optional[str] = None
    imageSrc: Optional[str] = None
    imageName: Optional[str] = None
    decorationType: Optional[str] = None
    widgetType: Optional[str] = None
    x: float = Field(50, ge=-100, le=200)
    y: float = Field(50, ge=-100, le=200)
    width: Optional[float] = Field(None, ge=1, le=3840)
    height: Optional[float] = Field(None, ge=1, le=3840)
    rotation: float = 0
    scale: float = Field(1, ge=0.05, le=8)
    zIndex: int = 0
    color: Optional[str] = None
    fontFamily: Optional[str] = None
    fontSize: Optional[float] = Field(None, ge=6, le=280)
    fontWeight: Optional[str] = None
    fontStyle: Optional[Literal["normal", "italic"]] = "normal"
    textAlign: Optional[Literal["left", "center", "right"]] = "center"
    textShadow: Optional[str] = "none"
    opacity: float = Field(1, ge=0, le=1)
    startTime: float = Field(0, ge=0)
    endTime: float = Field(1, ge=0)
    fadeInDuration: float = Field(0, ge=0)
    fadeOutDuration: float = Field(0, ge=0)
    animationType: Literal["fade", "slide-up", "zoom", "rotate-in", "none"] = "fade"
    voiceoverText: Optional[str] = None
    audioSegments: List[VisualAudioSegment] = Field(default_factory=list)


class VisualProject(BaseModel):
    title: str = Field("可视编辑项目", min_length=1)
    description: str = ""
    weishi_caption: str = ""
    hashtags: List[str] = Field(default_factory=lambda: ["可视编辑", "MomentWeaver"])
    timelineDuration: float = Field(15.0, ge=1.0, le=300.0)
    canvas: VisualCanvasSpec = Field(default_factory=VisualCanvasSpec)
    background: VisualBackgroundConfig = Field(default_factory=VisualBackgroundConfig)
    elements: List[VisualCanvasElement] = Field(default_factory=list)
    source: str = "video-background-board"


class VisualRenderRequest(BaseModel):
    project: VisualProject
    job_id: Optional[str] = None


class VisualRenderStatus(BaseModel):
    job_id: str
    status: Literal["submitted", "rendering", "rendered", "failed"] = "submitted"
    project_path: str = ""
    status_path: str = ""
    video_url: str = ""
    video_path: str = ""
    error: Optional[str] = None
    updated_at: str = ""


class VisualRenderResponse(VisualRenderStatus):
    publish_path: str = ""
    publish_text: str = ""
    message: str = ""
