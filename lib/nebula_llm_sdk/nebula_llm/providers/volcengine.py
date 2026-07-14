import asyncio
import json
from typing import Any, Dict, List
import httpx

from ..base import ExecutionResult
from .openai import OpenAIProvider
from ..types import ModelInfo
from ..logger import logger

class VolcengineProvider(OpenAIProvider):
    async def execute(
        self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> ExecutionResult:
        base_url = options.get("base_url") or "https://ark.cn-beijing.volces.com/api/v3"
        base_url = base_url.rstrip("/")
        
        task_type = options.get("type", model_config.type)

        if task_type == "image":
            return await self._execute_volcengine_image(
                base_url, api_key, model_config, prompt, options
            )
        
        if task_type == "video":
            return await self._execute_volcengine_video(
                base_url, api_key, model_config, prompt, options
            )
        
        return await super().execute(model_config, api_key, prompt, messages, options)

    async def _execute_volcengine_image(
        self, base_url: str, api_key: str, model_config: ModelInfo, prompt: str, options: Dict[str, Any],
    ) -> ExecutionResult:
        url = f"{base_url}/images/generations"

        size = options.get("size", "2K")
        if options.get("resolution"):
            size = options.get("resolution")
        elif options.get("quality") == 'hd':
            size = "2K"

        payload = {
            "model": model_config.target_model_id,
            "prompt": prompt,
            "image": (options.get("images") and len(options["images"]) > 0) and options["images"] or None,
            "size": size,
            "response_format": "url", 
            "n": options.get("n", 1) or options.get("count", 1)
        }
        if not payload.get("image"):
            del payload["image"]

        input_images = options.get("images", [])
        if input_images and len(input_images) > 0:
            payload["image"] = input_images

        upstream = model_config.upstream_params or {}
        for k, v in upstream.items():
            payload[k] = v
            
        if payload["n"] > 1:
            payload["sequential_image_generation"] = "auto"

        for k in ["protocol", "type", "count", "aspectRatio", "aspect_ratio", "resolution", "image_url", "images"]:
             if k in payload: del payload[k]

        logger.info(f"[Volcengine] Image Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )

            if response.status_code != 200:
                error_text = await response.text()
                logger.error(f"Volcengine Image Error ({response.status_code}): {error_text}")
                raise Exception(f"Volcengine Image Error: {error_text[:200]}")

            data = response.json()
            assets = []
            
            if "data" in data:
                for item in data["data"]:
                    if "url" in item:
                        assets.append(item["url"])
                    elif "image_url" in item:
                        assets.append(item["image_url"])
                    elif "b64_json" in item:
                        assets.append(f"data:image/png;base64,{item['b64_json']}")

            return ExecutionResult(assets=assets, usage={"input": 0, "output": 0})

    async def _execute_volcengine_video(
        self, base_url: str, api_key: str, model_config: ModelInfo, prompt: str, options: Dict[str, Any],
    ) -> ExecutionResult:
        url_create = f"{base_url}/contents/generations/tasks"
        
        content_list: List[Dict[str, Any]] = [
            {"type": "text", "text": prompt}
        ]

        input_images = options.get("images", [])
        model_id = model_config.target_model_id
        
        is_lite_ref = "lite" in model_id and "i2v" in model_id

        if input_images:
            for idx, img_url in enumerate(input_images):
                image_item = {
                    "type": "image_url",
                    "image_url": {"url": img_url}
                }
                if is_lite_ref:
                     image_item["role"] = "reference_image"
                else:
                    if idx == 0:
                        image_item["role"] = "first_frame"
                    elif idx == 1:
                        image_item["role"] = "last_frame"
                content_list.append(image_item)

        payload = {
            "model": model_id,
            "content": content_list,
            "ratio": options.get("ratio") or options.get("aspectRatio") or "16:9",
            "duration": options.get("duration", 5),
            "watermark": False,
            **(model_config.upstream_params or {})
        }
        
        if isinstance(payload["duration"], str):
             try:
                 payload["duration"] = int(payload["duration"].replace("s", ""))
             except:
                 payload["duration"] = 5

        logger.info(f"[Volcengine] Video Create Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp_create = await client.post(
                url_create,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )

            if resp_create.status_code != 200:
                error_text = await resp_create.text()
                logger.error(f"Volcengine Video Create Error: {error_text}")
                raise Exception(f"Video Creation Failed: {error_text[:200]}")

            task_data = resp_create.json()
            task_id = task_data.get("id")
            if not task_id:
                raise Exception("No Task ID returned from Volcengine")

            url_get = f"{url_create}/{task_id}"
            logger.info(f"[Volcengine] Polling Task: {task_id}")
            
            video_url = ""
            max_retries = 60
            
            for _ in range(max_retries):
                await asyncio.sleep(2)
                
                resp_get = await client.get(
                    url_get,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if resp_get.status_code != 200:
                    continue
                
                task_info = resp_get.json()
                status = task_info.get("status")
                
                if status == "succeeded":
                    content = task_info.get("content", {})
                    video_url = content.get("video_url")
                    break
                elif status == "failed":
                    error_msg = task_info.get("error", {}).get("message", "Unknown error")
                    raise Exception(f"Video Generation Failed: {error_msg}")
            
            if not video_url:
                raise Exception("Video generation timed out")
            
            return ExecutionResult(assets=[video_url], usage={"input": 0, "output": 0})
