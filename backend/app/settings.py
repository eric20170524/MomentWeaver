from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
VBOARD_DIST_DIR = REPO_ROOT / "video-background-board" / "dist"
LEGACY_FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIR = VBOARD_DIST_DIR if VBOARD_DIST_DIR.exists() else LEGACY_FRONTEND_DIR
STORAGE_DIR = Path(os.getenv("MOMENTWEAVER_STORAGE", PROJECT_ROOT / "storage")).resolve()
JOBS_DIR = STORAGE_DIR / "jobs"
DOCS_EXAMPLES_DIR = REPO_ROOT / "docs" / "朋友圈分享转微视"
LIB_DIR = PROJECT_ROOT / "lib"
DEFAULT_NEBULA_SDK_PATH = LIB_DIR / "nebula_llm_sdk"
DEFAULT_SMART_ASSET_KIT_PATH = LIB_DIR / "smart-asset-kit"


def _project_path_from_env(key: str, default: Path) -> Path:
    raw_value = os.getenv(key, "").strip()
    if not raw_value:
        return default.resolve()
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


NEBULA_SDK_PATH = _project_path_from_env("NEBULA_SDK_PATH", DEFAULT_NEBULA_SDK_PATH)
SMART_ASSET_KIT_PATH = _project_path_from_env(
    "SMART_ASSET_KIT_PATH",
    DEFAULT_SMART_ASSET_KIT_PATH,
)


def get_nebula_sdk_path() -> Path:
    return _project_path_from_env("NEBULA_SDK_PATH", DEFAULT_NEBULA_SDK_PATH)


def get_smart_asset_kit_path() -> Path:
    return _project_path_from_env(
        "SMART_ASSET_KIT_PATH",
        DEFAULT_SMART_ASSET_KIT_PATH,
    )


def ensure_storage() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def job_dir(job_id: str) -> Path:
    ensure_storage()
    return JOBS_DIR / job_id
