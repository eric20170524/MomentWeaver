import json
from typing import Any, AsyncGenerator, Dict, List
import httpx

from ..base import ExecutionResult, LLMProvider
from ..types import ModelInfo
from ..logger import logger

class OpenAIProvider(LLMProvider):
    async def execute(
        self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> ExecutionResult:
        base_url = options.get("base_url") or "https://api.openai.com/v1"
        base_url = base_url.rstrip("/")

        task_type = options.get("type", model_config.type)

        if task_type == "image":
            return await self._execute_image(
                base_url, api_key, model_config, prompt, options
            )

        return await self._execute_chat(
            base_url, api_key, model_config, prompt, messages, options
        )

    async def execute_stream(
        self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> AsyncGenerator[str, None]:
        base_url = options.get("base_url") or "https://api.openai.com/v1"
        base_url = base_url.rstrip("/")
        url = f"{base_url}/chat/completions"

        system_content = options.get("system_prompt") or "You are a helpful assistant."
        
        if messages:
            for m in messages:
                if m.get("role") == "model":
                    m["role"] = "assistant"
            has_system = any(m.get("role") == "system" for m in messages)
            final_messages = messages
            if not has_system:
                final_messages = [{"role": "system", "content": system_content}] + messages
        else:
            final_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]

        upstream_params = model_config.upstream_params or {}
        payload = {
            "model": model_config.target_model_id,
            "messages": final_messages,
            "temperature": options.get("temperature", 0.7),
            "stream": True,
            **upstream_params,
        }
        
        if options.get("tools"):
            payload["tools"] = options["tools"]
            payload["tool_choice"] = "auto"

        payload.pop("protocol", None)

        logger.info(f"[OpenAI] Stream Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST", url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload, timeout=300.0,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"OpenAI Stream Error ({response.status_code}): {error_text.decode()}")
                    yield f"Error: {error_text.decode()}"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            json_data = json.loads(data)
                            if not json_data.get("choices"):
                                continue
                            delta = json_data["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]
                        except Exception as e:
                            logger.error(f"Error parsing OpenAI stream: {e}")
                            continue

    async def _execute_chat(
        self, base_url: str, api_key: str, model_config: ModelInfo, prompt: str,
        messages: List[Dict[str, Any]], options: Dict[str, Any],
    ) -> ExecutionResult:
        url = f"{base_url}/chat/completions"
        system_content = options.get("system_prompt") or "You are a helpful assistant."

        if messages:
            for m in messages:
                if m.get("role") == "model":
                    m["role"] = "assistant"
            has_system = any(m.get("role") == "system" for m in messages)
            final_messages = messages
            if not has_system:
                final_messages = [{"role": "system", "content": system_content}] + messages
        else:
            final_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]

        if options.get("images") and len(options["images"]) > 0:
            if final_messages and final_messages[-1]["role"] == "user":
                content_parts = [{"type": "text", "text": str(final_messages[-1]["content"])}]
                for img in options["images"]:
                    content_parts.append({"type": "image_url", "image_url": {"url": img}})
                final_messages[-1]["content"] = content_parts  # type: ignore

        upstream_params = model_config.upstream_params or {}
        payload = {
            "model": model_config.target_model_id,
            "messages": final_messages,
            "temperature": options.get("temperature", 0.7),
            "stream": False,
            **upstream_params,
        }
        payload.pop("protocol", None)

        logger.info(f"[OpenAI] Chat Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if response.status_code != 200:
                logger.error(f"OpenAI Error ({response.status_code}): {response.text}")
                raise Exception(f"OpenAI Error ({response.status_code}): {response.text}")

            data = response.json()
            return ExecutionResult(
                content=data["choices"][0]["message"]["content"],
                usage={
                    "input": data.get("usage", {}).get("prompt_tokens", 0),
                    "output": data.get("usage", {}).get("completion_tokens", 0),
                },
            )

    async def _execute_image(
        self, base_url: str, api_key: str, model_config: ModelInfo, prompt: str, options: Dict[str, Any],
    ) -> ExecutionResult:
        url = f"{base_url}/images/generations"

        size = options.get("size", "1024x1024")
        if not options.get("size") and options.get("aspect_ratio"):
            ar = options["aspect_ratio"]
            if ar == "16:9":
                size = "1792x1024"
            elif ar == "9:16":
                size = "1024x1792"

        upstream_params = model_config.upstream_params or {}
        payload = {
            "model": model_config.target_model_id,
            "prompt": prompt,
            "n": options.get("n", 1),
            "size": size,
            "response_format": "b64_json",
            "quality": options.get("quality", "standard"),
            "style": options.get("style", "vivid"),
            **upstream_params,
        }

        for k in ["protocol", "type", "count", "images", "image_url", "params", "aspect_ratio", "resolution"]:
            payload.pop(k, None)

        logger.info(f"[OpenAI] Image Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if response.status_code != 200:
                logger.error(f"OpenAI Image Error ({response.status_code}): {response.text}")
                raise Exception(f"OpenAI Image Error ({response.status_code}): {response.text}")

            data = response.json()
            assets = []
            for item in data["data"]:
                if "b64_json" in item:
                    assets.append(f"data:image/png;base64,{item['b64_json']}")
                elif "url" in item:
                    assets.append(item["url"])

            return ExecutionResult(assets=assets, usage={"input": 0, "output": 0})
