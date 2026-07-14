import json
import mimetypes
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


@dataclass
class AssetSearchResult:
    source: str
    target: str
    keywords: str
    url: str
    license_hint: str
    focus: str
    notes: str
    score: int = 0
    rank: int = 0
    recommended: bool = False
    score_reasons: Optional[List[str]] = None


@dataclass
class AssetDownloadResult:
    source: str
    status: str
    saved_path: str
    manifest_path: str
    message: str


VALID_ASSET_SOURCES = (
    "opengameart",
    "kenney",
    "itch",
    "gameart2d",
    "craftpix",
    "lospec",
    "spritelib",
)

_ZH_KEYWORDS = {
    "像素风": "pixel art",
    "角色包": "character pack",
    "角色": "character",
    "精灵动画": "sprite animation",
    "精灵表": "sprite sheet",
    "精灵": "sprite",
    "动画": "animation",
    "三国": "ancient",
    "街机": "arcade",
    "主角": "hero",
    "怪物": "monster",
    "敌人": "enemy",
    "敌将": "boss",
    "关卡": "level",
    "地图": "tilemap",
    "地形": "tileset",
    "瓦片": "tileset",
    "图块": "tileset",
    "像素": "pixel",
    "界面": "ui",
    "按钮": "ui button",
    "图标": "icon",
    "道具": "props",
    "物件": "props",
    "武器": "weapon",
    "特效": "vfx",
    "刀光": "slash vfx",
    "火焰": "fire vfx",
    "爆炸": "explosion vfx",
    "森林": "forest",
    "城堡": "castle",
    "水寨": "warship",
}

_TARGET_ALIASES = {
    "sprite": "sprites",
    "sprites": "sprites",
    "spritesheet": "sprites",
    "sprite-sheet": "sprites",
    "sprite-animation": "sprites",
    "animation": "sprites",
    "character": "characters",
    "characters": "characters",
    "character-pack": "characters",
    "character-packs": "characters",
    "hero": "characters",
    "enemy": "characters",
    "tile": "tilesets",
    "tiles": "tilesets",
    "tileset": "tilesets",
    "tilesets": "tilesets",
    "tilemap": "tilesets",
    "pixel": "pixel-art",
    "pixel-art": "pixel-art",
    "pixelart": "pixel-art",
    "ui": "ui",
    "hud": "ui",
    "interface": "ui",
    "button": "ui",
    "buttons": "ui",
    "prop": "props",
    "props": "props",
    "item": "props",
    "items": "props",
    "vfx": "vfx",
    "effect": "vfx",
    "effects": "vfx",
    "particles": "vfx",
}

_TARGET_FOCUS = {
    "sprites": "2D sprite sheets and animation frames",
    "characters": "2D character packs, heroes, enemies, and NPC sprites",
    "tilesets": "2D tilesets, tilemaps, terrain, and level blocks",
    "pixel-art": "pixel-art sprites, packs, and reusable game art",
    "ui": "2D UI, HUD, icons, buttons, and menus",
    "props": "2D props, items, weapons, pickups, and scene objects",
    "vfx": "2D VFX spritesheets, hit effects, slash effects, and particles",
}

_TARGET_QUERY_TERMS = {
    "sprites": ("sprite",),
    "characters": ("character",),
    "tilesets": ("tileset",),
    "pixel-art": ("pixel", "art"),
    "ui": ("ui",),
    "props": ("props",),
    "vfx": ("vfx",),
}

_SOURCE_LICENSE_HINTS = {
    "opengameart": "Mixed CC0/CC-BY/OGA-BY; check each asset page.",
    "kenney": "Kenney assets are commonly CC0; verify the selected pack page.",
    "itch": "Mixed creator licenses; filter free assets and check each page.",
    "gameart2d": "Freebie and commercial terms vary; check the asset page.",
    "craftpix": "Freebie and premium terms vary; check the asset page.",
    "lospec": "Mixed community licenses; check each sprite or pack page.",
    "spritelib": "Classic free sprite library; verify attribution and reuse terms.",
}

_SOURCE_FOCUS = {
    "opengameart": "open game art library with tags and license metadata",
    "kenney": "consistent CC0-friendly game asset packs",
    "itch": "indie 2D game asset packs and complete sprite collections",
    "gameart2d": "cartoon platformer, UI, tileset, and character freebies",
    "craftpix": "polished 2D packs, UI, character, monster, and tileset freebies",
    "lospec": "pixel-art-focused sprites, palettes, and small packs",
    "spritelib": "browse-only classic 2D sprite catalog",
}

_SOURCE_BASE_SCORES = {
    "kenney": 82,
    "opengameart": 78,
    "itch": 74,
    "craftpix": 68,
    "gameart2d": 66,
    "lospec": 64,
    "spritelib": 56,
}

_SOURCE_LICENSE_BONUS = {
    "kenney": 10,
    "opengameart": 7,
    "itch": 3,
    "gameart2d": 2,
    "craftpix": 2,
    "lospec": 3,
    "spritelib": 2,
}

_TARGET_SOURCE_BONUS = {
    "sprites": {"opengameart": 8, "itch": 7, "kenney": 6, "craftpix": 5, "gameart2d": 4, "lospec": 3},
    "characters": {"itch": 9, "opengameart": 8, "craftpix": 6, "gameart2d": 6, "kenney": 4},
    "tilesets": {"kenney": 10, "opengameart": 7, "itch": 5, "craftpix": 5, "gameart2d": 3, "lospec": 3},
    "pixel-art": {"lospec": 12, "opengameart": 8, "itch": 7, "kenney": 4, "spritelib": 4},
    "ui": {"kenney": 11, "craftpix": 6, "gameart2d": 6, "opengameart": 4, "itch": 4},
    "props": {"kenney": 9, "opengameart": 6, "itch": 5, "craftpix": 5, "gameart2d": 3},
    "vfx": {"opengameart": 9, "itch": 6, "craftpix": 5, "gameart2d": 4, "lospec": 3},
}

_DIRECT_DOWNLOAD_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".aseprite",
    ".psd",
    ".kra",
    ".tmx",
    ".tsx",
    ".json",
}

def sanitize_keywords(text: str, max_words: int = 4) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s-]+", " ", text)
    words = [word for word in re.split(r"\s+", text) if word]
    return " ".join(words[:max_words])


def fallback_keywords(prompt: str, max_words: int = 4) -> str:
    prompt = (prompt or "").strip()
    ascii_words = sanitize_keywords(prompt, max_words=max_words)
    mapped: List[str] = []
    for zh, en in _ZH_KEYWORDS.items():
        if zh in prompt:
            mapped.extend(en.split())
    if mapped:
        return " ".join(list(dict.fromkeys(mapped).keys())[:max_words])
    return ascii_words or "2d game assets"


async def extract_keywords(prompt: str, keyword: Optional[str] = None, provider: Optional[str] = None) -> str:
    if keyword:
        return sanitize_keywords(keyword)

    try:
        from smart_asset_kit.core.config import load_config
        from smart_asset_kit.llm.client import AIClient

        cfg = load_config()
        client_text = AIClient(model_type="text", provider=provider or cfg.provider)
        instruction = (
            "Extract the core 2D game art search keywords from the following text and "
            "translate them into English keywords separated by spaces. Focus on sprites, "
            "character packs, tilesets, pixel art, UI, props, or VFX only. Max 4 words. "
            f"Do not include punctuation or explanations. Text: {prompt}"
        )
        result = await client_text.generate_asset(instruction)
        content = getattr(result, "content", "") or ""
        keywords = sanitize_keywords(content)
        if keywords:
            return keywords
    except Exception:
        pass

    return fallback_keywords(prompt)


def normalize_target(target: str) -> str:
    normalized = sanitize_keywords(target, max_words=3).replace(" ", "-")
    return _TARGET_ALIASES.get(normalized, "sprites")


def _build_query(keywords: str, target: str) -> str:
    words: List[str] = []
    query_text = f"{keywords} {' '.join(_TARGET_QUERY_TERMS[target])}"
    for word in re.split(r"\s+", sanitize_keywords(query_text, max_words=12)):
        if word and word not in words:
            words.append(word)
    return " ".join(words)


def _source_url(source: str, query: str) -> str:
    safe_query = urllib.parse.quote(query)
    if source == "opengameart":
        return (
            "https://opengameart.org/art-search-advanced?"
            f"keys={safe_query}&field_art_type_tid%5B%5D=9"
            "&sort_by=count&sort_order=DESC"
        )
    if source == "kenney":
        return f"https://kenney.nl/assets?q={safe_query}"
    if source == "itch":
        return f"https://itch.io/game-assets/free/tag-2d?q={safe_query}"
    if source == "gameart2d":
        return f"https://www.gameart2d.com/freebies.html?search={safe_query}"
    if source == "craftpix":
        return f"https://craftpix.net/?s={safe_query}"
    if source == "lospec":
        return f"https://lospec.com/sprite-list?search={safe_query}"
    return "https://www.widgetworx.com/widgetworx/portfolio/spritelib.html"


def _keyword_words(keywords: str) -> List[str]:
    return [word for word in re.split(r"\s+", sanitize_keywords(keywords, max_words=16)) if word]


def score_asset_result(source: str, target: str, keywords: str) -> Tuple[int, List[str]]:
    normalized_target = normalize_target(target)
    words = set(_keyword_words(keywords))
    score = _SOURCE_BASE_SCORES[source]
    reasons = [f"{source} baseline fit for 2D asset discovery"]

    license_bonus = _SOURCE_LICENSE_BONUS.get(source, 0)
    if license_bonus:
        score += license_bonus
        reasons.append("clearer license/provenance triage")

    target_bonus = _TARGET_SOURCE_BONUS.get(normalized_target, {}).get(source, 0)
    if target_bonus:
        score += target_bonus
        reasons.append(f"strong source fit for {normalized_target}")

    target_terms = set(_TARGET_QUERY_TERMS[normalized_target])
    if words.intersection(target_terms):
        score += 4
        reasons.append("query already matches the selected 2D target")

    if {"pack", "sheet", "spritesheet", "tileset"}.intersection(words):
        if source in {"kenney", "itch", "opengameart", "craftpix"}:
            score += 3
            reasons.append("good chance of complete downloadable packs")
        if source == "spritelib":
            score -= 4
            reasons.append("browse catalog may need more manual filtering")

    if "pixel" in words and source == "lospec":
        score += 6
        reasons.append("pixel-art specialist source")

    if normalized_target == "ui" and source in {"kenney", "craftpix", "gameart2d"}:
        score += 3
        reasons.append("source commonly has UI/HUD sets")

    return max(0, min(score, 100)), reasons[:4]


def build_asset_search_results(keywords: str, target: str = "sprites") -> List[AssetSearchResult]:
    normalized_target = normalize_target(target)
    safe_keywords = sanitize_keywords(keywords) or fallback_keywords(keywords)
    query = _build_query(safe_keywords, normalized_target)
    focus = _TARGET_FOCUS[normalized_target]

    results = []
    for source in VALID_ASSET_SOURCES:
        score, score_reasons = score_asset_result(source, normalized_target, safe_keywords)
        results.append(
            AssetSearchResult(
                source=source,
                target=normalized_target,
                keywords=safe_keywords,
                url=_source_url(source, query),
                license_hint=_SOURCE_LICENSE_HINTS[source],
                focus=focus,
                notes=f"{_SOURCE_FOCUS[source]}; verify final license and attribution on the asset page.",
                score=score,
                score_reasons=score_reasons,
            )
        )

    return rank_asset_results(results)


def rank_asset_results(
    results: Iterable[AssetSearchResult],
    recommendation_limit: int = 3,
) -> List[AssetSearchResult]:
    results = list(results)
    results.sort(key=lambda result: (-result.score, VALID_ASSET_SOURCES.index(result.source)))
    recommendation_limit = max(0, min(recommendation_limit, len(results)))
    for idx, result in enumerate(results, start=1):
        result.rank = idx
        result.recommended = idx <= recommendation_limit
    return results


def get_recommended_results(results: Iterable[AssetSearchResult], limit: int = 3) -> List[AssetSearchResult]:
    sorted_results = sorted(results, key=lambda result: (result.rank or 999, -result.score))
    return [result for result in sorted_results if result.recommended][:limit]


def filter_sources(results: Iterable[AssetSearchResult], source: str) -> List[AssetSearchResult]:
    normalized_source = (source or "all").strip().lower()
    if normalized_source == "all":
        return rank_asset_results(results)
    return rank_asset_results(result for result in results if result.source == normalized_source)


def write_results_json(results: Iterable[AssetSearchResult], path: str) -> None:
    out_path = Path(path)
    if out_path.parent:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(result) for result in results], f, indent=2, ensure_ascii=False)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    cleaned = cleaned.strip("-._")
    return cleaned or "asset"


def _url_extension(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return Path(parsed.path).suffix.lower()


def _is_direct_download_url(url: str) -> bool:
    return _url_extension(url) in _DIRECT_DOWNLOAD_EXTENSIONS


def _extension_from_content_type(content_type: str) -> str:
    if not content_type:
        return ""
    guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ""


def _write_shortcut(path: Path, url: str) -> None:
    path.write_text(f"[InternetShortcut]\nURL={url}\n", encoding="utf-8")


def download_asset_result(
    result: AssetSearchResult,
    out_dir: str = "./output/images/asset-downloads",
    timeout: int = 30,
) -> AssetDownloadResult:
    rank_prefix = f"{result.rank:02d}" if result.rank else "asset"
    result_dir = Path(out_dir) / f"{rank_prefix}-{_safe_filename(result.source)}-{_safe_filename(result.target)}"
    result_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = result_dir / "asset_search_result.json"
    manifest_path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8")

    shortcut_path = result_dir / "source.url"
    _write_shortcut(shortcut_path, result.url)

    if not _is_direct_download_url(result.url):
        return AssetDownloadResult(
            source=result.source,
            status="manual_required",
            saved_path=str(shortcut_path),
            manifest_path=str(manifest_path),
            message="Saved source shortcut and manifest; this source URL is a browse/search page.",
        )

    request = urllib.request.Request(result.url, headers={"User-Agent": "smart-asset-kit/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            headers = getattr(response, "headers", None)
            content_type = ""
            if headers is not None:
                get_content_type = getattr(headers, "get_content_type", None)
                content_type = get_content_type() if get_content_type else headers.get("Content-Type", "")
            content_type = (content_type or "").lower()
            if content_type.startswith("text/html"):
                return AssetDownloadResult(
                    source=result.source,
                    status="manual_required",
                    saved_path=str(shortcut_path),
                    manifest_path=str(manifest_path),
                    message="Saved source shortcut and manifest; direct URL returned an HTML page.",
                )

            ext = _url_extension(result.url) or _extension_from_content_type(content_type) or ".bin"
            filename = f"{rank_prefix}-{_safe_filename(result.source)}-{_safe_filename(result.keywords)}{ext}"
            asset_path = result_dir / filename
            asset_path.write_bytes(response.read())

        return AssetDownloadResult(
            source=result.source,
            status="downloaded",
            saved_path=str(asset_path),
            manifest_path=str(manifest_path),
            message="Downloaded direct asset file and saved provenance manifest.",
        )
    except Exception as exc:
        return AssetDownloadResult(
            source=result.source,
            status="failed",
            saved_path=str(shortcut_path),
            manifest_path=str(manifest_path),
            message=f"Download failed; saved source shortcut and manifest instead. Error: {exc}",
        )


def download_recommended_assets(
    results: Iterable[AssetSearchResult],
    out_dir: str = "./output/images/asset-downloads",
    limit: int = 3,
    timeout: int = 30,
) -> List[AssetDownloadResult]:
    return [
        download_asset_result(result, out_dir=out_dir, timeout=timeout)
        for result in get_recommended_results(results, limit=limit)
    ]
