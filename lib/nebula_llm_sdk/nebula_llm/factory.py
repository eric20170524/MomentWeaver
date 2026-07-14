from typing import Optional

from .base import LLMProvider
from .types import ModelInfo, ChannelInfo
from .providers.gemini import GeminiProvider
from .providers.openai import OpenAIProvider
from .providers.volcengine import VolcengineProvider
from .providers.openrouter import OpenRouterProvider
from .providers.xai import XAIProvider
from .providers.elevenlabs import ElevenLabsProvider
from .providers.minimax import MinimaxProvider

class LLMFactory:
    @staticmethod
    def get_provider(
        model: ModelInfo, channel: Optional[ChannelInfo] = None
    ) -> LLMProvider:
        provider_type = model.provider.lower()

        if "google" in provider_type or "gemini" in provider_type:
            return GeminiProvider()

        if "volcengine" in provider_type or "doubao" in provider_type:
            return VolcengineProvider()
            
        if "openrouter" in provider_type:
            return OpenRouterProvider()

        if "xai" in provider_type or "grok" in provider_type:
            return XAIProvider()
            
        if "eleven" in provider_type:
            return ElevenLabsProvider()

        if "minimax" in provider_type:
            return MinimaxProvider()

        # Default fallback
        return OpenAIProvider()

    @staticmethod
    def get_api_key(model: ModelInfo, channel: Optional[ChannelInfo] = None) -> str:
        if channel:
            return channel.key
        return ""

    @staticmethod
    def get_base_url(model: ModelInfo, channel: Optional[ChannelInfo] = None) -> str:
        if channel and channel.base_url:
            return channel.base_url
        
        provider = model.provider.lower()
        if "openai" in provider:
            return "https://api.openai.com/v1"
        if "xai" in provider:
            return "https://api.x.ai/v1"
        if "minimax" in provider:
            return "https://api.minimaxi.com/v1"
            
        return ""
