import json
import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional

CONFIG_FILE = Path(os.getcwd()) / ".sak_config.json"

class SAKConfig(BaseModel):
    provider: str = "xai"
    xai_api_key: str = ""
    gemini_api_key: str = ""
    eleven_api_key: str = ""
    minimax_api_key: str = ""
    
    xai_image_model: str = "grok-imagine-image-pro"
    xai_video_model: str = "grok-imagine-video"
    xai_audio_model: str = "grok-audio"
    
    gemini_image_model: str = "imagen-3.0-generate-002"
    gemini_video_model: str = "veo-2.0-generate-001"
    gemini_audio_model: str = "gemini-2.5-flash"
    minimax_audio_model: str = "speech-2.8-hd"

def load_config() -> SAKConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return SAKConfig(**data)
        except Exception:
            return SAKConfig()
    return SAKConfig()

def save_config(config: SAKConfig):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config.model_dump(), f, indent=4)
