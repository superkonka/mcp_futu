from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    app_name: str = "富途 MCP API 服务"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # 富途 OpenD 配置
    futu_host: str = "127.0.0.1"
    futu_port: int = 65123  # OpenD API端口（行情/交易Context连接端口）
    futu_telnet_port: int = 65234  # OpenD Telnet端口（用于权限控制等）
    futu_ws_port: int = 33133  # OpenD WebSocket端口（如需使用WS通道）
    futu_ws_key: Optional[str] = "2e6972a1716376ab"  # WebSocket密钥（如开启WS鉴权）
    futu_unlock_password: Optional[str] = None  # 交易解锁密码
    
    # MCP 服务配置
    mcp_name: str = "futu-mcp-server"
    mcp_version: str = "1.0.0"
    
    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    
    # 行情数据缓存配置
    cache_enabled: bool = True
    cache_expire_seconds: int = 60
    
    # 第三方API密钥（仅本地环境变量）
    metaso_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()