import re
import os
import json
import zipfile
import requests
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urljoin
from dataclasses import dataclass, asdict
from smart_asset_kit.llm.client import AIClient
from smart_asset_kit.core.config import load_config

@dataclass
class ScrapedAsset:
    title: str
    url: str
    source: str
    description: str
    preview_url: str
    download_urls: List[str]
    license: str
    score: float = 0.0
    reason: str = ""

# Request headers for web scraping
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def scrape_kenney(query: str, limit: int = 5) -> List[ScrapedAsset]:
    """Scrape Kenney 2D asset packs matching the query."""
    assets = []
    search_url = f"https://kenney.nl/assets?q={quote(query)}"
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        
        # Extract individual asset URLs
        raw_links = re.findall(r'href=["\']((?:https://kenney\.nl)?/assets/[a-zA-Z0-9-]+)["\']', r.text)
        detail_urls = []
        for l in raw_links:
            abs_url = urljoin("https://kenney.nl", l)
            if not any(x in abs_url for x in ["category:", "tag:", "upcoming", "feed", "search", "support", "donate", "licensing"]):
                if abs_url not in detail_urls:
                    detail_urls.append(abs_url)
        
        for url in detail_urls[:limit]:
            try:
                detail_r = requests.get(url, headers=HEADERS, timeout=15)
                if detail_r.status_code != 200:
                    continue
                
                # Title
                title_match = re.search(r'<title>([^<]+)</title>', detail_r.text)
                if title_match:
                    title_text = title_match.group(1).strip()
                    title = re.split(r'&middot;|\||-', title_text)[0].strip()
                else:
                    title = url.split("/")[-1].replace("-", " ").title()
                
                # Description
                desc_match = re.search(r'<meta name=["\']description["\'] content=["\']([^"\']+)["\']', detail_r.text)
                description = desc_match.group(1).strip() if desc_match else "Kenney asset pack."
                
                # Direct ZIP links
                zip_links = re.findall(r'href=["\']([^"\']+\.zip)["\']', detail_r.text)
                download_urls = [urljoin(url, dl) for dl in zip_links]
                # Filter duplicates
                download_urls = list(dict.fromkeys(download_urls))
                
                # Preview image
                preview_match = re.search(r'src=["\']([^"\']+/preview\.png)["\']', detail_r.text)
                preview_url = urljoin(url, preview_match.group(1)) if preview_match else ""
                if not preview_url:
                    # Find any png preview in the media paths
                    png_links = re.findall(r'src=["\']([^"\']+/media/pages/assets/[^"\']+\.png)["\']', detail_r.text)
                    if png_links:
                        preview_url = urljoin(url, png_links[0])
                
                assets.append(ScrapedAsset(
                    title=title,
                    url=url,
                    source="kenney",
                    description=description,
                    preview_url=preview_url,
                    download_urls=download_urls,
                    license="CC0 (Public Domain)"
                ))
            except Exception:
                continue
    except Exception:
        pass
    return assets

def scrape_opengameart(query: str, limit: int = 5) -> List[ScrapedAsset]:
    """Scrape OpenGameArt 2D assets matching the query."""
    assets = []
    # Limit to 2D Art (tid=9)
    search_url = f"https://opengameart.org/art-search-advanced?keys={quote(query)}&field_art_type_tid[]=9"
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        
        # Extract asset URLs
        raw_links = re.findall(r'href=["\'](/content/[a-zA-Z0-9-]+)["\']', r.text)
        detail_urls = []
        for l in raw_links:
            abs_url = urljoin("https://opengameart.org", l)
            if not any(x in abs_url for x in ["/faq", "/rules", "/irc-web-chat-rules"]):
                if abs_url not in detail_urls:
                    detail_urls.append(abs_url)
                    
        for url in detail_urls[:limit]:
            try:
                detail_r = requests.get(url, headers=HEADERS, timeout=15)
                if detail_r.status_code != 200:
                    continue
                
                # Title
                title_match = re.search(r'<h2 class=["\']title["\'] id=["\']page-title["\']>([^<]+)</h2>', detail_r.text)
                if not title_match:
                    title_match = re.search(r'<title>([^<]+) \| OpenGameArt\.org</title>', detail_r.text)
                title = title_match.group(1).strip() if title_match else url.split("/")[-1].replace("-", " ").title()
                
                # Description
                desc_match = re.search(r'<div class="field-item even" property="content:encoded">(.*?)</div>', detail_r.text, re.DOTALL)
                description = ""
                if desc_match:
                    description = re.sub(r'<[^>]+>', ' ', desc_match.group(1)) # strip HTML tags
                    description = re.sub(r'\s+', ' ', description).strip()
                if not description:
                    description = "OpenGameArt asset collection."
                if len(description) > 300:
                    description = description[:297] + "..."
                    
                # Download URLs (files under /sites/default/files)
                file_links = re.findall(r'href=["\']([^"\']+/sites/default/files/[^"\']+\.(?:zip|rar|7z|tar\.gz|png|jpg|jpeg|gif))["\']', detail_r.text)
                download_urls = [urljoin(url, dl) for dl in file_links]
                download_urls = list(dict.fromkeys(download_urls))
                
                # License
                license_links = re.findall(r'href=["\']([^"\']*/licenses/[^"\']+)["\']', detail_r.text)
                licenses = []
                for ll in license_links:
                    lic_name = ll.split("/")[-1].replace("-", " ").upper()
                    if lic_name and lic_name not in licenses:
                        licenses.append(lic_name)
                license_str = ", ".join(licenses) if licenses else "OGA Custom / Mixed License"
                
                # Preview url
                preview_url = ""
                # Find the first image download or preview image
                for dl in download_urls:
                    if dl.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                        preview_url = dl
                        break
                if not preview_url:
                    img_match = re.search(r'<img[^>]+src=["\']([^"\']+/sites/default/files/[^"\']+)["\']', detail_r.text)
                    if img_match:
                        preview_url = urljoin(url, img_match.group(1))
                        
                assets.append(ScrapedAsset(
                    title=title,
                    url=url,
                    source="opengameart",
                    description=description,
                    preview_url=preview_url,
                    download_urls=download_urls,
                    license=license_str
                ))
            except Exception:
                continue
    except Exception:
        pass
    return assets

def fallback_score_asset(prompt: str, asset: ScrapedAsset) -> Dict[str, Any]:
    """Score relevance using word overlap as a fallback mechanism."""
    prompt_words = [w.lower() for w in re.split(r'\W+', prompt) if len(w) > 2]
    if not prompt_words:
        return {"score": 5.0, "reason": "Evaluated using default fallback score."}
        
    text_to_search = (asset.title + " " + asset.description + " " + asset.license).lower()
    matches = 0
    for w in prompt_words:
        if w in text_to_search:
            matches += 1
            
    score = (matches / len(prompt_words)) * 10.0
    score = min(max(round(score, 1), 1.0), 10.0) # bound between 1.0 and 10.0
    return {
        "score": score,
        "reason": f"Matches {matches} out of {len(prompt_words)} keywords in the user query (Fallback match)."
    }

async def llm_score_asset(
    prompt: str,
    asset: ScrapedAsset,
    provider: Optional[str] = None,
    fallback_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Score the asset relevance using the configured LLM text model."""
    try:
        cfg = load_config()
        # For minimax, make sure to target MiniMax-M2.5 specifically if not overridden
        target = None
        current_provider = provider or cfg.provider
        if current_provider == "minimax":
            target = "MiniMax-M2.5"
            
        client = AIClient(model_type="text", provider=current_provider, target_model=target)
        
        system_prompt = (
            "You are an expert game developer. Evaluate the suitability of the following 2D game asset pack "
            f"for the developer's request: \"{prompt}\".\n\n"
            f"Asset Title: {asset.title}\n"
            f"Source: {asset.source}\n"
            f"Description: {asset.description}\n"
            f"License: {asset.license}\n\n"
            "Respond in JSON format with precisely two keys:\n"
            "\"score\": a float between 0.0 and 10.0 representing suitability (10.0 is perfect fit, 0.0 is completely irrelevant),\n"
            "\"reason\": a brief 1-2 sentence explanation of why it fits or does not fit.\n"
            "Provide ONLY the JSON block, no conversational prefix or suffix."
        )
        
        res = await client.generate_asset(system_prompt)
        content = getattr(res, "content", "") or ""
        
        # Extract JSON from output
        json_match = re.search(r'(\{.*\})', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
            score = float(data.get("score", 0.0))
            reason = str(data.get("reason", "No reason provided."))
            return {"score": round(score, 1), "reason": reason}
    except Exception as e:
        # Fallback to local matching if LLM fails
        pass
        
    return fallback_score_asset(fallback_prompt or prompt, asset)

async def search_and_rank_assets(
    prompt: str,
    source: str = "all",
    provider: Optional[str] = None,
    limit_per_source: int = 5,
    query: Optional[str] = None,
) -> List[ScrapedAsset]:
    """Search, scrape, score, and rank assets from Kenney and OpenGameArt."""
    assets = []
    search_query = query or prompt
    
    # Run scrapers in parallel
    loop = asyncio.get_event_loop()
    tasks = []
    if source in ["all", "kenney"]:
        tasks.append(loop.run_in_executor(None, scrape_kenney, search_query, limit_per_source))
    if source in ["all", "opengameart"]:
        tasks.append(loop.run_in_executor(None, scrape_opengameart, search_query, limit_per_source))
        
    results = await asyncio.gather(*tasks)
    for r in results:
        assets.extend(r)
        
    if not assets:
        return []
        
    # Perform scoring for all assets
    score_tasks = [llm_score_asset(prompt, asset, provider, fallback_prompt=search_query) for asset in assets]
    scores = await asyncio.gather(*score_tasks)
    
    # Assign scores
    for asset, score_data in zip(assets, scores):
        asset.score = score_data["score"]
        asset.reason = score_data["reason"]
        
    # Sort descending by score
    assets.sort(key=lambda x: x.score, reverse=True)
    return assets

async def download_asset(asset: ScrapedAsset, dest_dir: str) -> List[str]:
    """Download all file URLs in the asset pack, extracting ZIP files."""
    os.makedirs(dest_dir, exist_ok=True)
    manifest_path = os.path.join(dest_dir, "asset_search_result.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(asdict(asset), f, indent=2, ensure_ascii=False)
    shortcut_path = os.path.join(dest_dir, "source.url")
    with open(shortcut_path, "w", encoding="utf-8") as f:
        f.write(f"[InternetShortcut]\nURL={asset.url}\n")

    downloaded_files = [manifest_path, shortcut_path]

    def download_file(url: str):
        try:
            filename = url.split("/")[-1].split("?")[0]
            if not filename:
                filename = f"asset_{hash(url)}"
            target_path = os.path.join(dest_dir, filename)
            
            r = requests.get(url, headers=HEADERS, stream=True, timeout=30)
            if r.status_code == 200:
                with open(target_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                downloaded_files.append(target_path)

                if filename.lower().endswith(".zip") and zipfile.is_zipfile(target_path):
                    extract_path = os.path.join(dest_dir, filename.lower().replace(".zip", "_extracted"))
                    os.makedirs(extract_path, exist_ok=True)
                    with zipfile.ZipFile(target_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)
                    downloaded_files.append(extract_path)
        except Exception:
            pass
            
    await asyncio.gather(*[asyncio.to_thread(download_file, url) for url in asset.download_urls])
    return downloaded_files
