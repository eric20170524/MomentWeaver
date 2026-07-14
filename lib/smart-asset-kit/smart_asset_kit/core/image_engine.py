import asyncio
from typing import List, Optional
from rich.progress import Progress, SpinnerColumn, TextColumn
from smart_asset_kit.llm.client import AIClient
from smart_asset_kit.llm.prompts import Prompts

class ImageEngine:
    def __init__(self, client: AIClient):
        self.client = client
        self.text_client = AIClient(model_type="text")

    async def _enhance_prompt(self, raw_prompt: str) -> str:
        """Use text-model to enhance prompt."""
        enhance_prompt = Prompts.enhance_image_prompt(raw_prompt)
        res = await self.text_client.generate_asset(enhance_prompt)
        if res.content and len(res.content) > 10:
            return res.content.strip()
        return raw_prompt

    async def generate_batch(self, prompt: str, n: int = 1, options: dict = None, auto_enhance: bool = False) -> List[str]:
        """Generate static images."""
        if options is None:
            options = {}
            
        final_prompt = prompt
        
        if auto_enhance:
             try:
                 final_prompt = await self._enhance_prompt(prompt)
             except Exception:
                 pass # Keep original
                 
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            
            progress.add_task(description=f"Generating {n} image(s)...", total=None)
            
            try:
                if "resolution" in options:
                    options["size"] = options["resolution"]
                
                result = await self.client.generate_asset(final_prompt, n=n, **options)
                return result.assets
            except Exception as e:
                raise Exception(f"Image generation failed: {e}")

    async def generate_states(self, prompt: str, states: List[str], options: dict = None) -> dict:
        """Generate UI state variants."""
        if options is None: options = {}
        
        results = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            for state in states:
                progress.add_task(description=f"Generating {state} state...", total=None)
                state_prompt = f"{prompt}, specifically designed as the {state} state (e.g. {state} button state)."
                try:
                    result = await self.client.generate_asset(state_prompt, n=1, **options)
                    if result.assets:
                        results[state] = result.assets[0]
                except Exception as e:
                    results[state] = f"Error: {str(e)}"
        return results
