import asyncio
import json
import base64
import io
from urllib.parse import urlparse
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
import xai_sdk
from PIL import Image, ImageOps

from ..base import ExecutionResult
from .openai import OpenAIProvider
from ..types import ModelInfo
from ..logger import logger

class XAIProvider(OpenAIProvider):
    def _compress_image_data(self, data: bytes, max_edge: int = 1024, quality: int = 85) -> tuple[bytes, str]:
        try:
            img = Image.open(io.BytesIO(data))
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            width, height = img.size
            if width > max_edge or height > max_edge:
                ratio = min(max_edge / width, max_edge / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"[xAI] Resized image from {width}x{height} to {new_size}")
            
            out_buffer = io.BytesIO()
            img.save(out_buffer, format="JPEG", quality=quality)
            return out_buffer.getvalue(), "image/jpeg"
        except Exception as e:
            logger.warning(f"[xAI] Image compression failed, using original: {e}")
            return data, "image/jpeg"

    async def execute(
            self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> ExecutionResult:
        options["base_url"] = options.get("base_url") or "https://api.x.ai/v1"
        base_url = options["base_url"]
        
        task_type = options.get("type", model_config.type)
        target_model = model_config.target_model_id.lower()
        
        is_video = task_type == "video" or "video" in target_model
        is_image = task_type == "image" or "image" in target_model
        
        if is_video or is_image:
            parsed = urlparse(base_url)
            client = xai_sdk.AsyncClient(api_key=api_key)
            
            try:
                if is_video:
                    return await self._execute_video(client, model_config, prompt, options)
                else:
                    return await self._execute_image(client, model_config, prompt, options)
            finally:
                if hasattr(client, 'close'):
                    await client.close()
        
        return await super().execute(model_config, api_key, prompt, messages, options)
    
    async def execute_stream(
            self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> AsyncGenerator[str, None]:
        options["base_url"] = options.get("base_url") or "https://api.x.ai/v1"
        async for chunk in super().execute_stream(model_config, api_key, prompt, messages, options):
            yield chunk
    
    async def _execute_image(
            self, client: xai_sdk.AsyncClient, model_config: ModelInfo, prompt: str, options: Dict[str, Any],
    ) -> ExecutionResult:
        model = model_config.target_model_id
        n = options.get("n", 1)
        aspect_ratio = options.get("aspect_ratio") or options.get("aspectRatio")
        
        kwargs = {}
        if aspect_ratio:
            kwargs["aspect_ratio"] = aspect_ratio
            
        if model_config.upstream_params:
            kwargs.update(model_config.upstream_params)

        image_url = None
        input_images = options.get("images", [])
        
        if options.get("image_url"):
            input_images = [options["image_url"]]
            
        if input_images and len(input_images) > 0:
            img_src = input_images[0]
            if img_src.startswith(("http://", "https://")):
                try:
                    logger.info(f"[xAI] Downloading image for editing: {img_src}")
                    async with httpx.AsyncClient(timeout=30.0) as downloader:
                        img_resp = await downloader.get(img_src)
                        img_resp.raise_for_status()
                        compressed_data, mime = self._compress_image_data(img_resp.content)
                        b64_data = base64.b64encode(compressed_data).decode("utf-8")
                        image_url = f"data:{mime};base64,{b64_data}"
                except Exception as e:
                    logger.error(f"[xAI] Image processing failed: {e}")
                    image_url = img_src
            else:
                image_url = img_src

        assets = []
        logger.info(f"[xAI] Image Request (SDK): model={model}, prompt={prompt[:50]}..., n={n}, has_image={bool(image_url)}")

        if n > 1:
            responses = await client.image.sample_batch(
                prompt=prompt, model=model, image_url=image_url, n=n, **kwargs
            )
            for resp in responses:
                assets.append(resp.url)
        else:
            response = await client.image.sample(
                prompt=prompt, model=model, image_url=image_url, **kwargs
            )
            assets.append(response.url)
            
        return ExecutionResult(assets=assets, usage={"input": 0, "output": 0})
    
    async def _execute_video(
            self, client: xai_sdk.AsyncClient, model_config: ModelInfo, prompt: str, options: Dict[str, Any],
    ) -> ExecutionResult:
        model = model_config.target_model_id
        
        duration = options.get("duration")
        if duration and isinstance(duration, str):
             try:
                 duration = float(duration.replace("s", ""))
             except:
                 pass
                 
        aspect_ratio = options.get("aspect_ratio") or options.get("aspectRatio")
        resolution = options.get("resolution")

        kwargs = {}
        if model_config.upstream_params:
            kwargs.update(model_config.upstream_params)

        image_url = None
        video_url = None
        
        if options.get("video_url"):
            video_url = options["video_url"]
        
        input_images = options.get("images", [])
        if not video_url and input_images and len(input_images) > 0:
            img_src = input_images[0]
            if img_src.startswith(("http://", "https://")):
                try:
                    logger.info(f"[xAI] Downloading input image for video: {img_src}")
                    async with httpx.AsyncClient(timeout=30.0) as downloader:
                        img_resp = await downloader.get(img_src)
                        if img_resp.status_code == 200:
                            compressed_data, mime = self._compress_image_data(img_resp.content)
                            b64_data = base64.b64encode(compressed_data).decode("utf-8")
                            image_url = f"data:{mime};base64,{b64_data}"
                except Exception as e:
                    logger.error(f"[xAI] Video input image conversion failed: {e}")
                    image_url = img_src
            else:
                image_url = img_src
        
        if not video_url:
            if duration: kwargs["duration"] = duration
            if aspect_ratio: kwargs["aspect_ratio"] = aspect_ratio
            if resolution: kwargs["resolution"] = resolution

        logger.info(f"[xAI] Video Request (SDK): model={model}, prompt={prompt[:50]}..., has_video={bool(video_url)}, has_image={bool(image_url)}")
        
        response = await client.video.generate(
            prompt=prompt, model=model, image_url=image_url, video_url=video_url, **kwargs
        )
        
        result_url = response.url
        if not result_url:
             raise Exception("xAI SDK returned no video URL")

        return ExecutionResult(assets=[result_url], usage={"input": 0, "output": 0})
