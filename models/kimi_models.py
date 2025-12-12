"""
Kimi 模型 API 的请求和响应数据结构（基于月之暗面接口）
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class KimiChatMessage(BaseModel):
    """Kimi聊天消息模型"""
    role: Literal["user", "assistant", "system"] = Field(description="消息角色")
    content: str = Field(description="消息内容")


class KimiChatRequest(BaseModel):
    """Kimi聊天请求模型"""
    messages: List[KimiChatMessage] = Field(description="对话消息列表")
    model: str = Field(default="kimi-k2-thinking-turbo", description="模型类型")
    stream: bool = Field(default=False, description="是否流式响应")
    temperature: Optional[float] = Field(default=0.7, description="温度参数，控制随机性")
    max_tokens: Optional[int] = Field(default=2048, description="最大生成token数")


class KimiChatChoice(BaseModel):
    """Kimi聊天选择模型"""
    index: int = Field(description="选择索引")
    message: KimiChatMessage = Field(description="消息内容")
    finish_reason: Optional[str] = Field(default=None, description="结束原因")


class KimiChatUsage(BaseModel):
    """Kimi聊天使用量模型"""
    prompt_tokens: int = Field(description="提示token数")
    completion_tokens: int = Field(description="完成token数")
    total_tokens: int = Field(description="总token数")


class KimiChatResponse(BaseModel):
    """Kimi聊天响应模型"""
    id: str = Field(description="响应ID")
    object: str = Field(default="chat.completion", description="对象类型")
    created: int = Field(description="创建时间戳")
    model: str = Field(description="使用的模型")
    choices: List[KimiChatChoice] = Field(description="选择列表")
    usage: KimiChatUsage = Field(description="使用量信息")
