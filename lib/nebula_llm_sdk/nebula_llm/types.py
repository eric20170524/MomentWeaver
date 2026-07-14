from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ModelInfo(BaseModel):
    """
    轻量化的模型配置定义，替代原项目中的 LlmModel 数据库模型。
    """
    target_model_id: str
    provider: str
    type: str = "text"  # text, image, video
    upstream_params: Optional[Dict[str, Any]] = None

class ChannelInfo(BaseModel):
    """
    轻量化的渠道配置定义，替代原项目中的 ApiChannel 数据库模型。
    """
    key: str
    base_url: Optional[str] = None
    type: str = "openai"
