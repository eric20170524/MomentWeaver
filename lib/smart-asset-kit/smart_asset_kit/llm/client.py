from nebula_llm.factory import LLMFactory
from nebula_llm.types import ModelInfo
from smart_asset_kit.core.config import load_config
from typing import Optional, Dict, Any

class AIClient:
    def __init__(self, provider: Optional[str] = None, target_model: Optional[str] = None, api_key: Optional[str] = None, model_type: str = "image"):
        config = load_config()
        
        self.provider_name = provider or config.provider
        
        if not target_model:
            if self.provider_name == "xai":
                if model_type == "image":
                    target_model = config.xai_image_model
                elif model_type == "video":
                    target_model = config.xai_video_model
                elif model_type == "audio":
                    target_model = config.xai_audio_model
                elif model_type == "text":
                    target_model = "grok-2"
                else:
                    target_model = "grok-2"
            elif self.provider_name == "minimax":
                if model_type == "audio":
                    target_model = config.minimax_audio_model
                elif model_type == "text":
                    target_model = "MiniMax-M2.5"
                else:
                    target_model = "speech-2.8-hd"
            else:
                if model_type == "image":
                    target_model = config.gemini_image_model
                elif model_type == "video":
                    target_model = config.gemini_video_model
                elif model_type == "audio":
                    target_model = config.gemini_audio_model
                elif model_type == "text":
                    target_model = "gemini-2.5-flash"
                else:
                    target_model = "gemini-2.5-flash"
                
        self.target_model = target_model
        
        # 自动根据 provider 选用对应的 api key
        if self.provider_name == "xai":
            auto_key = config.xai_api_key
        elif self.provider_name == "gemini":
            auto_key = config.gemini_api_key
        elif self.provider_name == "eleven":
            auto_key = config.eleven_api_key
        elif self.provider_name == "minimax":
            auto_key = config.minimax_api_key
        elif self.provider_name == "local":
            auto_key = "local-no-key"
        else:
            auto_key = config.gemini_api_key
            
        self.api_key = api_key or auto_key
        
        if self.provider_name != "local" and not self.api_key:
            raise ValueError(f"API Key for {self.provider_name} is missing. Please configure it in settings.")

        if self.provider_name == "local":
            self.provider = None # Local doesn't need a nebula provider
            return
            
        self.model_info = ModelInfo(
            target_model_id=self.target_model,
            provider=self.provider_name,
            type=model_type
        )
        
        self.provider = LLMFactory.get_provider(self.model_info)

    async def generate_asset(self, prompt: str, **kwargs) -> Any:
        result = await self.provider.execute(
            model_config=self.model_info,
            api_key=self.api_key,
            prompt=prompt,
            options=kwargs
        )
        return result
