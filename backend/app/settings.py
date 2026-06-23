from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STORAGE_DIR = Path(os.getenv("MOMENTWEAVER_STORAGE", PROJECT_ROOT / "storage")).resolve()
JOBS_DIR = STORAGE_DIR / "jobs"
DOCS_EXAMPLES_DIR = REPO_ROOT / "docs" / "朋友圈分享转微视"
MINIGAME_MASTER_DIR = Path("/Users/lm/pyProj/hungry-for-knowledge/minigame_master")
DEFAULT_NEBULA_SDK_PATH = MINIGAME_MASTER_DIR / "nebula_llm_sdk"
DEFAULT_SMART_ASSET_KIT_PATH = MINIGAME_MASTER_DIR / "smart-asset-kit"

NEBULA_SDK_PATH = Path(
    os.getenv("NEBULA_SDK_PATH", DEFAULT_NEBULA_SDK_PATH)
).resolve()

SMART_ASSET_KIT_PATH = Path(
    os.getenv(
        "SMART_ASSET_KIT_PATH",
        DEFAULT_SMART_ASSET_KIT_PATH,
    )
).resolve()


def get_nebula_sdk_path() -> Path:
    return Path(os.getenv("NEBULA_SDK_PATH", DEFAULT_NEBULA_SDK_PATH)).resolve()


def get_smart_asset_kit_path() -> Path:
    return Path(
        os.getenv(
            "SMART_ASSET_KIT_PATH",
            DEFAULT_SMART_ASSET_KIT_PATH,
        )
    ).resolve()


def ensure_storage() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def job_dir(job_id: str) -> Path:
    ensure_storage()
    return JOBS_DIR / job_id
