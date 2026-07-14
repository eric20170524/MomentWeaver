import json
import re
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class AudioSearchResult:
    source: str
    target: str
    keywords: str
    url: str


_ZH_KEYWORDS = {
    "古风": "asian",
    "中国": "chinese",
    "三国": "ancient battle",
    "战斗": "battle",
    "决战": "final battle",
    "史诗": "epic",
    "紧张": "tension",
    "激烈": "action",
    "码头": "dock",
    "江岸": "river",
    "水寨": "warship",
    "楼船": "warship",
    "火": "fire",
    "密林": "forest",
    "森林": "forest",
    "山道": "mountain",
    "营门": "gate",
    "栈桥": "bridge",
    "鼓": "drums",
    "古筝": "guzheng",
    "竹笛": "bamboo flute",
    "琵琶": "pipa",
    "背景音乐": "music",
    "配乐": "music",
    "音效": "sound effect",
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
    return ascii_words or "game music"


async def extract_keywords(prompt: str, keyword: Optional[str] = None, provider: Optional[str] = None) -> str:
    if keyword:
        return sanitize_keywords(keyword)

    try:
        from smart_asset_kit.core.config import load_config
        from smart_asset_kit.llm.client import AIClient

        cfg = load_config()
        client_text = AIClient(model_type="text", provider=provider or cfg.provider)
        instruction = (
            "Extract the core search keywords from the following text and translate them "
            "into English keywords separated by spaces. Max 4 words. Do not include "
            f"punctuation or explanations. Text: {prompt}"
        )
        result = await client_text.generate_asset(instruction)
        content = getattr(result, "content", "") or ""
        keywords = sanitize_keywords(content)
        if keywords:
            return keywords
    except Exception:
        pass

    return fallback_keywords(prompt)


def build_audio_search_results(keywords: str, target: str = "music") -> List[AudioSearchResult]:
    normalized_target = "sound-effects" if target in {"sfx", "sound", "sound-effects"} else "music"
    safe_keywords = urllib.parse.quote(keywords)
    oga_type = "13" if normalized_target == "sound-effects" else "12"
    return [
        AudioSearchResult(
            source="pixabay",
            target=normalized_target,
            keywords=keywords,
            url=f"https://pixabay.com/{normalized_target}/search/{safe_keywords}/",
        ),
        AudioSearchResult(
            source="opengameart",
            target=normalized_target,
            keywords=keywords,
            url=(
                "https://opengameart.org/art-search-advanced?"
                f"keys={safe_keywords}&field_art_type_tid%5B%5D={oga_type}"
                "&sort_by=count&sort_order=DESC"
            ),
        ),
    ]


def filter_sources(results: Iterable[AudioSearchResult], source: str) -> List[AudioSearchResult]:
    if source == "all":
        return list(results)
    return [result for result in results if result.source == source]


def write_results_json(results: Iterable[AudioSearchResult], path: str) -> None:
    out_path = Path(path)
    if out_path.parent:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(result) for result in results], f, indent=2, ensure_ascii=False)
