from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Union
from enum import Enum


class MCPRequestType(str, Enum):
    """MCP 请求类型"""
    INITIALIZE = "initialize"
    CALL_TOOL = "call_tool"
    LIST_TOOLS = "list_tools"
    GET_PROMPT = "get_prompt"
    LIST_PROMPTS = "list_prompts"


class MCPResponseType(str, Enum):
    """MCP 响应类型"""
    RESULT = "result"
    ERROR = "error"


class MCPError(BaseModel):
    """MCP 错误信息"""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class MCPRequest(BaseModel):
    """MCP 请求基础模型"""
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """MCP 响应基础模型"""
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class ToolResult(BaseModel):
    """工具执行结果"""
    content: List[Dict[str, Any]]
    isError: Optional[bool] = False


class MCPInitializeParams(BaseModel):
    """MCP 初始化参数"""
    protocolVersion: str
    capabilities: Dict[str, Any]
    clientInfo: Dict[str, str]


class MCPInitializeResult(BaseModel):
    """MCP 初始化结果"""
    protocolVersion: str = "2024-11-05"
    capabilities: Dict[str, Any]
    serverInfo: Dict[str, str] 