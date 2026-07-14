from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel

from .types import ModelInfo

class ExecutionResult(BaseModel):
    content: Optional[str] = None
    assets: Optional[List[str]] = None
    usage: Optional[Dict[str, int]] = None

class LLMProvider(ABC):
    @staticmethod
    def sanitize_payload(data: Any) -> Any:
        """
        Recursively sanitize payload for logging.
        Truncate long strings (text or base64 images) to first 10 chars + length.
        """
        if isinstance(data, dict):
            return {k: LLMProvider.sanitize_payload(v) for k, v in data.items()}
        if isinstance(data, list):
            return [LLMProvider.sanitize_payload(item) for item in data]
        if isinstance(data, str):
            # Threshold: if longer than 100 chars, truncate to 10 chars + length info
            if len(data) > 100:
                return data[:10] + f"...(len={len(data)})"
            return data
        return data

    @abstractmethod
    async def execute(
        self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> ExecutionResult:
        pass

    @abstractmethod
    async def execute_stream(
        self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> AsyncGenerator[str, None]:
        pass
