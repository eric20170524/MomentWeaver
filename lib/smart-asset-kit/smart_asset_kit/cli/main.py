import typer
import asyncio
import os
import re
from typing import Optional, List
from rich.console import Console
from smart_asset_kit.core.config import load_config, save_config
from smart_asset_kit.llm.client import AIClient
from smart_asset_kit.core.image_engine import ImageEngine
from smart_asset_kit.core.video_engine import VideoEngine
from smart_asset_kit.core.audio_engine import AudioEngine
from smart_asset_kit.core.audio_search import (
    build_audio_search_results,
    extract_keywords as extract_audio_keywords,
    filter_sources as filter_audio_sources,
    write_results_json as write_audio_results_json,
)
from smart_asset_kit.core.asset_search import (
    VALID_ASSET_SOURCES,
    build_asset_search_results,
    download_recommended_assets,
    extract_keywords as extract_asset_keywords,
    filter_sources as filter_asset_sources,
    write_results_json as write_asset_results_json,
)
import base64

app = typer.Typer(help="Smart Asset Kit (SAK) - Game and Media Asset Generator")
console = Console()

def save_b64(b64_str: str, path: str):
    if b64_str.startswith("data:"):
        b64_str = b64_str.split(",")[1]
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64_str))

@app.command()
def config(
    xai_key: Optional[str] = typer.Option(None, "--xai-key", help="API Key for Grok (XAI)"),
    gemini_key: Optional[str] = typer.Option(None, "--gemini-key", help="API Key for Gemini"),
    eleven_key: Optional[str] = typer.Option(None, "--eleven-key", help="API Key for ElevenLabs"),
    minimax_key: Optional[str] = typer.Option(None, "--minimax-key", help="API Key for MiniMax"),
    provider: Optional[str] = typer.Option(None, "--provider", help="Default provider name (e.g., xai, gemini)"),
    xai_image: Optional[str] = typer.Option(None, "--xai-image", help="Default XAI image model ID"),
    xai_video: Optional[str] = typer.Option(None, "--xai-video", help="Default XAI video model ID"),
    xai_audio: Optional[str] = typer.Option(None, "--xai-audio", help="Default XAI audio model ID"),
    gemini_image: Optional[str] = typer.Option(None, "--gemini-image", help="Default Gemini image model ID"),
    gemini_video: Optional[str] = typer.Option(None, "--gemini-video", help="Default Gemini video model ID"),
    gemini_audio: Optional[str] = typer.Option(None, "--gemini-audio", help="Default Gemini audio model ID"),
    minimax_audio: Optional[str] = typer.Option(None, "--minimax-audio", help="Default MiniMax audio model ID")
):
    """Configure SAK settings (API keys, default models)."""
    cfg = load_config()
    
    if xai_key: cfg.xai_api_key = xai_key
    if gemini_key: cfg.gemini_api_key = gemini_key
    if eleven_key: cfg.eleven_api_key = eleven_key
    if minimax_key: cfg.minimax_api_key = minimax_key
    if provider: cfg.provider = provider
    
    if xai_image: cfg.xai_image_model = xai_image
    if xai_video: cfg.xai_video_model = xai_video
    if xai_audio: cfg.xai_audio_model = xai_audio
    
    if gemini_image: cfg.gemini_image_model = gemini_image
    if gemini_video: cfg.gemini_video_model = gemini_video
    if gemini_audio: cfg.gemini_audio_model = gemini_audio
    if minimax_audio: cfg.minimax_audio_model = minimax_audio
    
    save_config(cfg)
    console.print(f"[green]Configuration saved successfully.[/green]")
    console.print(f"[dim]{cfg.model_dump_json(indent=2)}[/dim]")

@app.command()
def gen_image(
    prompt: str,
    model: Optional[str] = typer.Option(None, "--model", help="Override default model"),
    out_dir: str = typer.Option("./assets/images", "--out-dir", help="Output directory"),
    batch: int = typer.Option(1, "--batch", "-n", help="Number of images to generate"),
    auto_enhance: bool = typer.Option(False, "--enhance", help="Auto enhance prompt"),
    states: Optional[str] = typer.Option(None, "--states", help="Comma-separated UI states to generate (e.g. hover,pressed)")
):
    """Generate a static image asset."""
    os.makedirs(out_dir, exist_ok=True)
    
    async def run_gen():
        client = AIClient(model_type="image", target_model=model)
        engine = ImageEngine(client)
        
        if states:
             state_list = [s.strip() for s in states.split(",")]
             console.print(f"[blue]Generating UI states:[/blue] {state_list}")
             try:
                 results = await engine.generate_states(prompt, state_list)
                 for state, asset_url in results.items():
                     console.print(f"[green]{state}:[/green] {asset_url[:50]}...")
                     if asset_url.startswith("data:image"):
                         save_b64(asset_url, f"{out_dir}/img_{state}.png")
             except Exception as e:
                 console.print(f"[red]Error:[/red] {e}")
             return
             
        try:
            assets = await engine.generate_batch(prompt, n=batch, auto_enhance=auto_enhance)
            for i, asset_url in enumerate(assets):
                console.print(f"[green]Result {i+1}:[/green] {asset_url[:50]}...")
                if asset_url.startswith("data:image"):
                    save_b64(asset_url, f"{out_dir}/img_{i}.png")
                else:
                    console.print(f"[yellow]To download:[/yellow] {asset_url}")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            
    asyncio.run(run_gen())

@app.command()
def gen_video(
    prompt: str,
    model: Optional[str] = typer.Option(None, "--model", help="Override default model"),
    image: Optional[str] = typer.Option(None, "--ref", help="Reference image path/url"),
    extract_sheet: bool = typer.Option(False, "--spritesheet", help="Extract sprite sheet from video"),
    grid: str = typer.Option("4x4", "--grid", help="Grid size for sprite sheet e.g. 4x4"),
    out_dir: str = typer.Option("./output/video", "--out-dir", help="Output directory")
):
    """Generate a dynamic video/VFX asset."""
    os.makedirs(out_dir, exist_ok=True)
    async def run_gen():
        client = AIClient(model_type="video", target_model=model)
        engine = VideoEngine(client)
        opts = {}
        if image:
             opts["image"] = image # This will be handled by VideoEngine as local or remote
             
        try:
            assets = await engine.generate_vfx(prompt, options=opts)
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as downloader:
                for i, asset_url in enumerate(assets):
                    console.print(f"[green]Video URL:[/green] {asset_url}")
                    if asset_url.startswith("http"):
                        ext = os.path.splitext(asset_url.split("?")[0])[1] or ".mp4"
                        out_path = f"{out_dir}/video_{i}{ext}"
                        console.print(f"📥 Downloading to {out_path}...")
                        resp = await downloader.get(asset_url)
                        if resp.status_code == 200:
                            with open(out_path, "wb") as f:
                                f.write(resp.content)
                            console.print(f"✅ Downloaded.")
                            if extract_sheet:
                                 sheet_path = f"{out_dir}/sheet_{i}.png"
                                 grid_parts = [int(x) for x in grid.split("x")]
                                 engine.extract_spritesheet(out_path, sheet_path, grid_size=(grid_parts[0], grid_parts[1]))
                                 console.print(f"✅ Spritesheet created: {sheet_path}")
                        else:
                            console.print(f"[red]Download failed: {resp.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            
    asyncio.run(run_gen())

@app.command()
def clone_voice(
    name: str,
    file: str,
    description: str = typer.Option("", "--desc", help="Description of the voice"),
    provider: str = typer.Option("eleven", "--provider", help="Cloning provider (eleven, minimax)")
):
    """Clone a voice from an audio file (ElevenLabs or MiniMax)."""
    async def run_clone():
        client = AIClient(model_type="audio", provider=provider)
        engine = AudioEngine(client)
        try:
            voice_id = await engine.add_voice(name, file, description)
            console.print(f"[green]Voice cloned successfully![/green]")
            console.print(f"Voice ID: [bold]{voice_id}[/bold]")
            console.print(f"You can now use this ID with gen-audio --voice {voice_id}")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            
    asyncio.run(run_clone())

@app.command()
def gen_audio(
    prompt: str = typer.Argument("placeholder", help="TTS Prompt"),
    voice: str = typer.Option("ara", "--voice", help="TTS Voice or ID (e.g. Grandpa for local)"),
    provider: Optional[str] = typer.Option(None, "--provider", help="Override provider (e.g. eleven, gemini, minimax, local)"),
    file: Optional[str] = typer.Option(None, "--file", help="Input file for post-processing"),
    seamless: bool = typer.Option(False, "--seamless", help="Apply zero-crossing crossfade for BGM loops"),
    out_path: str = typer.Option("./output/audio/output.mp3", "--out", help="Output file path")
):
    """Generate an audio asset (TTS or BGM)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    async def run_gen():
        client = AIClient(model_type="audio", provider=provider)
        engine = AudioEngine(client)
        try:
             audio_bytes = None
             if file and os.path.exists(file):
                 with open(file, "rb") as f:
                     audio_bytes = f.read()
                 console.print(f"[blue]Loaded existing file: {file}[/blue]")
             elif provider == "local" or client.provider_name == "local":
                 audio_bytes = await engine.local_say(prompt, voice=voice)
                 with open(out_path, "wb") as f:
                     f.write(audio_bytes)
                 console.print(f"[green]Audio generated locally and saved to {out_path}[/green]")
             else:
                 res = await engine.generate_tts(prompt, voice=voice)
                 if res.startswith("data:audio"):
                     import base64
                     audio_bytes = base64.b64decode(res.split(",")[1])
                     with open(out_path, "wb") as f:
                         f.write(audio_bytes)
                     console.print(f"[green]Audio saved to {out_path}[/green]")
                 else:
                     console.print(f"[green]Audio Result:[/green] {res[:50]}...")
             
             if audio_bytes and seamless:
                 console.print("🔄 Applying seamless loop...")
                 fmt = (file or out_path).split(".")[-1]
                 looped = engine.create_seamless_loop(audio_bytes, format=fmt)
                 with open(out_path, "wb") as f:
                     f.write(looped)
                 console.print(f"✅ Seamless loop applied to {out_path}.")
        except Exception as e:
             console.print(f"[red]Error:[/red] {e}")
             
    asyncio.run(run_gen())

@app.command()
def search_audio(
    prompt: str = typer.Argument(..., help="BGM/SFX description, Chinese or English"),
    target: str = typer.Option("music", "--target", help="Search target: music or sound-effects"),
    source: str = typer.Option("all", "--source", help="Search source: all, pixabay, opengameart"),
    keyword: Optional[str] = typer.Option(None, "--keyword", help="Skip LLM keyword extraction and use these English keywords"),
    provider: Optional[str] = typer.Option(None, "--provider", help="Provider used for keyword extraction"),
    out: Optional[str] = typer.Option(None, "--out", help="Optional JSON output path"),
    open_browser: bool = typer.Option(False, "--open", help="Open the first result in a browser")
):
    """Search royalty-free/open game audio by extracting compact English keywords."""

    async def run_search():
        keywords = await extract_audio_keywords(prompt, keyword=keyword, provider=provider)
        results = filter_audio_sources(build_audio_search_results(keywords, target=target), source)
        if not results:
            console.print(f"[red]Unknown source:[/red] {source}. Use all, pixabay, or opengameart.")
            raise typer.Exit(1)

        console.print(f"[green]Keywords:[/green] {keywords}")
        for result in results:
            console.print(f"[bold]{result.source}[/bold] ({result.target}): {result.url}")

        if out:
            write_audio_results_json(results, out)
            console.print(f"[green]Search results saved to {out}[/green]")

        if open_browser:
            import webbrowser
            webbrowser.open(results[0].url)

    asyncio.run(run_search())

@app.command()
def search_assets(
    prompt: str = typer.Argument(..., help="2D game asset description, Chinese or English"),
    target: str = typer.Option(
        "sprites",
        "--target",
        help="Search target: sprites, characters, tilesets, pixel-art, ui, props, or vfx",
    ),
    source: str = typer.Option(
        "all",
        "--source",
        help="Search source: all, opengameart, kenney, itch, gameart2d, craftpix, lospec, spritelib",
    ),
    keyword: Optional[str] = typer.Option(
        None,
        "--keyword",
        help="Skip LLM keyword extraction and use these English keywords",
    ),
    provider: Optional[str] = typer.Option(None, "--provider", help="Provider used for keyword extraction"),
    out: Optional[str] = typer.Option(None, "--out", help="Optional JSON output path"),
    top: int = typer.Option(3, "--top", help="Number of top recommendations to mark/display"),
    download_top: int = typer.Option(0, "--download-top", help="Download/capture top N recommendations locally"),
    download_dir: str = typer.Option(
        "./output/images/asset-downloads",
        "--download-dir",
        help="Directory for downloaded/captured 2D asset recommendations",
    ),
    open_browser: bool = typer.Option(False, "--open", help="Open the first result in a browser"),
    deep: bool = typer.Option(False, "--deep", help="Run active scraping and LLM-based scoring/ranking")
):
    """Search, score, recommend, and optionally download/capture 2D game art candidates."""

    async def run_search():
        if deep:
            console.print("[blue]🔍 Performing deep scraping, LLM rating, and scoring...[/blue]")
            src_filter = "all"
            if source in ["kenney", "opengameart"]:
                src_filter = source
            elif source != "all":
                console.print(f"[yellow]⚠️ Deep search is optimized for 'kenney' and 'opengameart'. Running on all supported sources...[/yellow]")
                
            keywords = await extract_asset_keywords(prompt, keyword=keyword, provider=provider)
            from smart_asset_kit.core.asset_scorer import search_and_rank_assets, download_asset
            ranked_assets = await search_and_rank_assets(prompt, source=src_filter, provider=provider, query=keywords)
            
            if not ranked_assets:
                console.print("[yellow]No assets found or scored. Please refine your query.[/yellow]")
                return
                
            from rich.table import Table
            table = Table(title=f"🏆 Top Recommendations for: {prompt}")
            table.add_column("Rank", justify="center", style="bold cyan")
            table.add_column("Score", justify="center", style="bold green")
            table.add_column("Title", style="magenta")
            table.add_column("Source", style="cyan")
            table.add_column("License", style="yellow")
            table.add_column("Reason")
            
            display_limit = max(1, min(top, len(ranked_assets)))
            for idx, asset in enumerate(ranked_assets[:display_limit]):
                table.add_row(
                    str(idx + 1),
                    f"{asset.score:.1f}",
                    asset.title,
                    asset.source,
                    asset.license,
                    asset.reason
                )
            console.print(table)
            
            if out:
                import json
                from dataclasses import asdict
                os.makedirs(os.path.dirname(out) if os.path.dirname(out) else '.', exist_ok=True)
                with open(out, "w", encoding="utf-8") as f:
                    json.dump([asdict(a) for a in ranked_assets], f, indent=2, ensure_ascii=False)
                console.print(f"[green]Scored results saved to {out}[/green]")
                
            if download_top > 0:
                download_limit = min(download_top, len(ranked_assets))
                for i in range(download_limit):
                    asset = ranked_assets[i]
                    safe_title = re.sub(r"[^a-zA-Z0-9._-]+", "-", asset.title.lower()).strip("-._") or "asset"
                    dest = os.path.join(download_dir, f"{i+1:02d}-{asset.source}-{safe_title}")
                    console.print(f"📥 Downloading recommended asset #{i+1}: [bold]{asset.title}[/bold]...")
                    files = await download_asset(asset, dest)
                    if files:
                        console.print(f"✅ Success! Asset files downloaded and extracted to: [green]{dest}[/green]")
                    else:
                        console.print(f"[red]❌ Download failed for {asset.title}[/red]")
            return

        keywords = await extract_asset_keywords(prompt, keyword=keyword, provider=provider)
        results = filter_asset_sources(build_asset_search_results(keywords, target=target), source)
        if not results:
            valid_sources = ", ".join(("all", *VALID_ASSET_SOURCES))
            console.print(f"[red]Unknown source:[/red] {source}. Use {valid_sources}.")
            raise typer.Exit(1)

        recommendation_limit = max(0, min(top, len(results)))
        for idx, result in enumerate(results, start=1):
            result.rank = idx
            result.recommended = idx <= recommendation_limit

        console.print(f"[green]Keywords:[/green] {keywords}")
        for result in results:
            badge = " [green]TOP[/green]" if result.recommended else ""
            reasons = "; ".join(result.score_reasons or [])
            console.print(
                f"[bold]#{result.rank} {result.source}[/bold] "
                f"({result.target}, score {result.score}/100){badge}: {result.url}"
            )
            console.print(f"[dim]License:[/dim] {result.license_hint}")
            console.print(f"[dim]Focus:[/dim] {result.focus}")
            console.print(f"[dim]Why:[/dim] {reasons}")
            console.print(f"[dim]Notes:[/dim] {result.notes}")

        if out:
            write_asset_results_json(results, out)
            console.print(f"[green]Search results saved to {out}[/green]")

        if download_top:
            download_limit = max(0, min(download_top, recommendation_limit or len(results)))
            downloads = download_recommended_assets(results, out_dir=download_dir, limit=download_limit)
            for download in downloads:
                color = "green" if download.status == "downloaded" else "yellow"
                console.print(
                    f"[{color}]{download.status}[/{color}] {download.source}: "
                    f"{download.saved_path} ({download.message})"
                )

        if open_browser:
            import webbrowser
            webbrowser.open(results[0].url)

    asyncio.run(run_search())

@app.command()
def gui():
    """Launch the Smart Asset Kit GUI."""
    import sys
    try:
        from PySide6.QtWidgets import QApplication
        from smart_asset_kit.gui.main_window import MainWindow
        
        qt_app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(qt_app.exec())
    except ImportError:
        console.print("[red]Error:[/red] PySide6 is not installed. Please install it using 'pip install PySide6'.")

if __name__ == "__main__":
    app()
