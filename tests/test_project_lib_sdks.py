from __future__ import annotations

import os
from pathlib import Path

from app import settings
from app.music_assets import _build_pythonpath


def test_default_sdk_paths_live_under_project_lib(monkeypatch) -> None:
    monkeypatch.delenv("NEBULA_SDK_PATH", raising=False)
    monkeypatch.delenv("SMART_ASSET_KIT_PATH", raising=False)

    assert settings.get_nebula_sdk_path() == (
        settings.PROJECT_ROOT / "lib" / "nebula_llm_sdk"
    ).resolve()
    assert settings.get_smart_asset_kit_path() == (
        settings.PROJECT_ROOT / "lib" / "smart-asset-kit"
    ).resolve()


def test_relative_sdk_env_paths_resolve_from_project_root(monkeypatch) -> None:
    monkeypatch.setenv("NEBULA_SDK_PATH", "lib/custom-nebula")
    monkeypatch.setenv("SMART_ASSET_KIT_PATH", "lib/custom-sak")

    assert settings.get_nebula_sdk_path() == (
        settings.PROJECT_ROOT / "lib" / "custom-nebula"
    ).resolve()
    assert settings.get_smart_asset_kit_path() == (
        settings.PROJECT_ROOT / "lib" / "custom-sak"
    ).resolve()


def test_sak_pythonpath_includes_sak_and_nebula_paths() -> None:
    existing = os.pathsep.join(["/already", "/there"])

    pythonpath = _build_pythonpath(
        [Path("/moment/lib/smart-asset-kit"), Path("/moment/lib/nebula_llm_sdk")],
        existing,
    )

    assert pythonpath.split(os.pathsep) == [
        "/moment/lib/smart-asset-kit",
        "/moment/lib/nebula_llm_sdk",
        "/already",
        "/there",
    ]


def test_sdk_lib_dirs_are_installed_package_layouts() -> None:
    nebula_path = settings.PROJECT_ROOT / "lib" / "nebula_llm_sdk"
    sak_path = settings.PROJECT_ROOT / "lib" / "smart-asset-kit"

    assert (nebula_path / "nebula_llm").is_dir()
    assert (nebula_path / "nebula_llm_sdk-0.1.0.dist-info" / "METADATA").is_file()
    assert (sak_path / "smart_asset_kit").is_dir()
    assert (sak_path / "smart_asset_kit-0.1.0.dist-info" / "METADATA").is_file()

    for source_checkout_marker in [
        nebula_path / "pyproject.toml",
        nebula_path / "README.md",
        nebula_path / "tests",
        sak_path / "pyproject.toml",
        sak_path / "README.md",
        sak_path / "tests",
        sak_path / "doc",
    ]:
        assert not source_checkout_marker.exists()
