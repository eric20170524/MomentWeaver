from typing import Any, AsyncGenerator, Dict, List
import base64
import json

from google import genai
from google.genai import types

from ..base import ExecutionResult, LLMProvider
from ..types import ModelInfo
from ..logger import logger

class GeminiProvider(LLMProvider):
    async def execute(
            self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = None, options: Dict[str, Any] = None
    ) -> ExecutionResult:
        if messages is None: messages = []
        if options is None: options = {}
        
        logger.info(f"[Gemini] Execute {model_config.target_model_id} via new google-genai SDK")
        
        import os
        # Temporarily hide Vertex AI related environment variables to force Google AI Studio usage
        hidden_envs = {}
        for k in ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"]:
            if k in os.environ:
                hidden_envs[k] = os.environ.pop(k)

        try:
            client = genai.Client(api_key=api_key, vertexai=False)
        finally:
            for k, v in hidden_envs.items():
                os.environ[k] = v
        
        config_kwargs = {}
        if "temperature" in options:
            config_kwargs["temperature"] = options["temperature"]
        if "max_tokens" in options:
            config_kwargs["max_output_tokens"] = options["max_tokens"]
        if options.get("response_format") and options["response_format"].get("type") == "json_object":
            config_kwargs["response_mime_type"] = "application/json"
        if "system_prompt" in options:
            config_kwargs["system_instruction"] = options["system_prompt"]
        
        # Audio modality handling for Gemini
        if model_config.type == "audio" or "tts" in model_config.target_model_id:
            config_kwargs["response_modalities"] = ["AUDIO"]
            
        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
        
        contents = []
        if messages:
            for m in messages:
                role = m.get("role", "user")
                if role == "assistant":
                    role = "model"
                
                parts = []
                content_val = m.get("content", "")
                
                if isinstance(content_val, list):
                    for p in content_val:
                        if p.get("type") == "text":
                            parts.append(types.Part.from_text(text=p.get("text", "")))
                        elif p.get("type") == "image_url":
                            img_url = p.get("image_url", {}).get("url", "")
                            if "base64," in img_url:
                                b64_data = img_url.split("base64,")[1]
                                mime = "image/png"
                                if "image/jpeg" in img_url: mime = "image/jpeg"
                                parts.append(types.Part.from_bytes(data=base64.b64decode(b64_data), mime_type=mime))
                else:
                    parts.append(types.Part.from_text(text=str(content_val)))
                
                contents.append(types.Content(role=role, parts=parts))
        else:
            parts = []
            if prompt:
                parts.append(types.Part.from_text(text=prompt))
                
            input_images = options.get("images", [])
            if input_images:
                for img_str in input_images:
                    if isinstance(img_str, str) and "base64," in img_str:
                        b64_data = img_str.split("base64,")[1]
                        mime_type = "image/png"
                        if "image/jpeg" in img_str: mime_type = "image/jpeg"
                        parts.append(types.Part.from_bytes(data=base64.b64decode(b64_data), mime_type=mime_type))
            contents.append(types.Content(role="user", parts=parts))
        
        try:
            response = await client.aio.models.generate_content(
                model=model_config.target_model_id,
                contents=contents,
                config=config
            )
        except Exception as e:
            logger.error(f"[Gemini] Generate Content Failed: {e}")
            raise e
        
        usage = {"input": 0, "output": 0}
        try:
            if response.usage_metadata:
                usage["input"] = response.usage_metadata.prompt_token_count or 0
                usage["output"] = response.usage_metadata.candidates_token_count or 0
        except:
            pass
            
        assets = []
        text_content = ""
        
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, 'inline_data', None):
                    # It's base64 audio or image
                    mime_type = part.inline_data.mime_type
                    b64_data = base64.b64encode(part.inline_data.data).decode("utf-8")
                    assets.append(f"data:{mime_type};base64,{b64_data}")
                elif getattr(part, 'text', None):
                    text_content += part.text

        # Fallback to response.text if assets is empty
        if not text_content and not assets:
            try:
                text_content = response.text
            except ValueError:
                pass
            
        return ExecutionResult(
            content=text_content,
            assets=assets,
            usage=usage,
        )

    async def execute_stream(
            self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = None, options: Dict[str, Any] = None
    ) -> AsyncGenerator[str, None]:
        if messages is None: messages = []
        if options is None: options = {}
        
        logger.info(f"[Gemini] Stream Start {model_config.target_model_id} via new google-genai SDK")
        import os
        # Temporarily hide Vertex AI related environment variables to force Google AI Studio usage
        hidden_envs = {}
        for k in ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"]:
            if k in os.environ:
                hidden_envs[k] = os.environ.pop(k)

        try:
            client = genai.Client(api_key=api_key, vertexai=False)
        finally:
            for k, v in hidden_envs.items():
                os.environ[k] = v
        
        try:
            response_stream = await client.aio.models.generate_content_stream(
                model=model_config.target_model_id,
                contents=prompt
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"[Gemini] Stream Exception: {e}")
            raise e
