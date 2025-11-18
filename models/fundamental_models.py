"""
基本面搜索模型
用于metaso搜索API的请求和响应数据结构
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class FundamentalSearchRequest(BaseModel):
    """基本面搜索请求模型"""
    q: str = Field(..., description="搜索关键词，如'影响小米股价的相关信息'")
    scope: str = Field(default="webpage", description="搜索范围，可选：webpage, news, all")
    includeSummary: bool = Field(default=False, description="是否包含摘要")
    size: int = Field(default=10, ge=1, le=50, description="返回结果数量，1-50")
    includeRawContent: bool = Field(default=False, description="是否包含原始内容")
    conciseSnippet: bool = Field(default=False, description="是否使用简洁摘要")
    
    
class SearchResultItem(BaseModel):
    """搜索结果项"""
    title: str = Field(..., description="结果标题")
    url: str = Field(..., description="结果链接")
    snippet: str = Field(..., description="内容摘要")
    source: Optional[str] = Field(None, description="来源网站")
    publish_time: Optional[str] = Field(None, description="发布时间")
    relevance_score: Optional[float] = Field(None, description="相关度评分")
    
    
class FundamentalSearchResponse(BaseModel):
    """基本面搜索响应模型"""
    query: str = Field(..., description="搜索关键词")
    total_results: int = Field(..., description="总结果数量")
    results: List[SearchResultItem] = Field(..., description="搜索结果列表")
    search_time: float = Field(..., description="搜索耗时（秒）")
    api_source: str = Field(default="metaso", description="API来源")
    timestamp: datetime = Field(default_factory=datetime.now, description="搜索时间戳")


# ==================== Metaso网页读取模型 ====================

class MetasoReaderRequest(BaseModel):
    """Metaso网页读取请求模型"""
    url: str = Field(..., description="要读取的网页URL")
    

class MetasoReaderResponse(BaseModel):
    """Metaso网页读取响应模型"""
    url: str = Field(..., description="读取的网页URL")
    content: str = Field(..., description="网页纯文本内容")
    title: Optional[str] = Field(None, description="网页标题")
    read_time: float = Field(..., description="读取耗时（秒）")
    content_length: int = Field(..., description="内容长度（字符数）")
    api_source: str = Field(default="metaso", description="API来源")
    timestamp: datetime = Field(default_factory=datetime.now, description="读取时间戳")


# ==================== Metaso问答模型 ====================

class Message(BaseModel):
    """对话消息模型"""
    role: str = Field(..., description="消息角色：user/assistant/system")
    content: str = Field(..., description="消息内容")


class MetasoChatRequest(BaseModel):
    """Metaso问答请求模型"""
    messages: List[Message] = Field(..., description="对话消息列表")
    model: str = Field(default="fast", description="模型类型：fast/normal")
    stream: bool = Field(default=True, description="是否流式响应")
    

class MetasoChatResponse(BaseModel):
    """Metaso问答响应模型"""
    answer: str = Field(..., description="回答内容")
    model: str = Field(..., description="使用的模型")
    messages: List[Message] = Field(..., description="完整对话历史")
    response_time: float = Field(..., description="响应耗时（秒）")
    is_stream: bool = Field(..., description="是否为流式响应")
    api_source: str = Field(default="metaso", description="API来源")
    timestamp: datetime = Field(default_factory=datetime.now, description="回答时间戳")