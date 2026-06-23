from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Dict

from .settings import PROJECT_ROOT


ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

ALLOWED_ENV_KEYS = [
    "MOMENTWEAVER_HOST",
    "MOMENTWEAVER_PORT",
    "MOMENTWEAVER_RELOAD",
    "MOMENTWEAVER_PYTHON",
    "NEBULA_API_KEY",
    "NEBULA_PROVIDER",
    "NEBULA_MODEL",
    "NEBULA_BASE_URL",
    "NEBULA_SDK_PATH",
    "SMART_ASSET_KIT_PATH",
    "SAK_PYTHON",
]

RESTART_REQUIRED_KEYS = {
    "MOMENTWEAVER_HOST",
    "MOMENTWEAVER_PORT",
    "MOMENTWEAVER_RELOAD",
    "MOMENTWEAVER_PYTHON",
}


def parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_ENV_KEYS:
            continue
        try:
            parsed = shlex.split(value, posix=True)
            values[key] = parsed[0] if parsed else ""
        except ValueError:
            values[key] = value.strip().strip("\"'")
    return values


def effective_settings() -> Dict[str, str]:
    values = parse_env_file(ENV_EXAMPLE_PATH)
    values.update(parse_env_file(ENV_PATH))
    for key in ALLOWED_ENV_KEYS:
        if key in os.environ:
            values[key] = os.environ.get(key, "")
    return {key: values.get(key, "") for key in ALLOWED_ENV_KEYS}


def load_env_file_into_process() -> None:
    for key, value in parse_env_file(ENV_PATH).items():
        os.environ[key] = value


def save_settings(values: Dict[str, str]) -> Dict[str, str]:
    clean = {
        key: str(values.get(key, "")).strip()
        for key in ALLOWED_ENV_KEYS
        if key in values
    }

    base_lines = []
    source = ENV_PATH if ENV_PATH.exists() else ENV_EXAMPLE_PATH
    if source.exists():
        base_lines = source.read_text(encoding="utf-8").splitlines()

    written = set()
    next_lines = []
    for line in base_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in ALLOWED_ENV_KEYS:
            value = clean.get(key, effective_settings().get(key, ""))
            next_lines.append(f"{key}={shlex.quote(value)}")
            written.add(key)
        else:
            next_lines.append(line)

    for key in ALLOWED_ENV_KEYS:
        if key not in written:
            next_lines.append(f"{key}={shlex.quote(clean.get(key, effective_settings().get(key, '')))}")

    ENV_PATH.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
    for key in ALLOWED_ENV_KEYS:
        os.environ[key] = clean.get(key, effective_settings().get(key, ""))
    return effective_settings()
