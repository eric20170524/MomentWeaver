import re
import json
import httpx
import asyncio
from typing import Any, Dict, List

from ..base import ExecutionResult
from .openai import OpenAIProvider
from ..types import ModelInfo
from ..logger import logger

class OpenRouterProvider(OpenAIProvider):
    async def execute(
            self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> ExecutionResult:
        base_url = options.get("base_url") or "https://openrouter.ai/api/v1"
        base_url = base_url.rstrip("/")
        
        task_type = options.get("type", model_config.type)
        target_model = model_config.target_model_id.lower()
        
        is_chat_to_image = (
                task_type == "image"
                or ("grok" in target_model)
                or ("chat" in target_model)
                or ("gemini" in target_model and "image" in target_model)
                or ("gpt" in target_model and "image" in target_model)
                or ("flux" in target_model)
        )
        
        if is_chat_to_image:
            return await self._execute_chat_to_image(
                base_url, api_key, model_config, prompt, options
            )
        
        return await super().execute(model_config, api_key, prompt, messages, options)
    
    async def _execute_chat_to_image(
            self,
            base_url: str,
            api_key: str,
            model_config: ModelInfo,
            prompt: str,
            options: Dict[str, Any],
    ) -> ExecutionResult:
        url = f"{base_url}/chat/completions"
        
        messages = [{"role": "user", "content": prompt}]
        
        if options.get("images") and len(options["images"]) > 0:
            content_parts = [{"type": "text", "text": prompt}]
            for img in options["images"]:
                content_parts.append({"type": "image_url", "image_url": {"url": img}})
            messages[0]["content"] = content_parts
        
        upstream_params = model_config.upstream_params or {}
        
        payload = {
            "model": model_config.target_model_id,
            "messages": messages,
            "stream": False,
            **upstream_params,
        }
        
        if "modalities" not in payload:
            payload["modalities"] = ["image", "text"]
        
        image_config = payload.get("image_config", {})
        
        ar = options.get("aspectRatio") or options.get("aspect_ratio")
        if ar:
            image_config["aspect_ratio"] = ar
        
        res = options.get("resolution") or options.get("size")
        if res:
            image_config["image_size"] = res
        
        if image_config:
            payload["image_config"] = image_config
        
        for k in ["protocol", "type", "count", "images", "image_url", "params", "aspect_ratio", "aspectRatio", "resolution", "size"]:
            payload.pop(k, None)
        
        logger.info(f"[OpenRouter] Requesting Image via Chat: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": options.get("http_referer", "https://nebula-ai.com"),
                    "X-Title": options.get("x_title", "Nebula AI Workspace")
                },
                json=payload,
            )
            
            raw_response = await response.aread()
            
            # --- Hook: on_error / on_success ---
            on_error = options.get("on_error")
            on_success = options.get("on_success")

            if response.status_code != 200:
                error_msg = raw_response.decode()
                logger.error(f"[OpenRouter] API Error ({response.status_code}): {error_msg}")
                if on_error and callable(on_error):
                    if asyncio.iscoroutinefunction(on_error):
                        await on_error(api_key, error_msg)
                    else:
                        on_error(api_key, error_msg)
                raise Exception(f"OpenRouter Error ({response.status_code}): {error_msg}")
            
            if on_success and callable(on_success):
                if asyncio.iscoroutinefunction(on_success):
                    await on_success(api_key)
                else:
                    on_success(api_key)
            
            try:
                data = json.loads(raw_response)
            except Exception as e:
                raise Exception(f"Invalid JSON response: {e}")
            
            assets = []
            content = ""
            usage = {
                "input": data.get("usage", {}).get("prompt_tokens", 0),
                "output": data.get("usage", {}).get("completion_tokens", 0),
            }
            
            if data.get("choices"):
                choice = data.get("choices", [])[0]
                message = choice.get("message", {})
                content = message.get("content", "")
                
                if "images" in message and message["images"]:
                    for img in message["images"]:
                        if isinstance(img, str):
                            assets.append(img)
                        elif isinstance(img, dict):
                            if "image_url" in img and "url" in img["image_url"]:
                                assets.append(img["image_url"]["url"])
                            elif "url" in img:
                                assets.append(img["url"])
                            elif "b64_json" in img:
                                assets.append(f"data:image/png;base64,{img['b64_json']}")
            
            if content and len(assets) == 0:
                matches = re.findall(r'!\[.*?\]\((https?://.*?)\)', content)
                if matches:
                    assets.extend(matches)
                    logger.info(f"[OpenRouter] Extracted {len(matches)} images from markdown")
            
            return ExecutionResult(
                content=content,
                assets=assets,
                usage=usage
            )
