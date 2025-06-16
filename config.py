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
    futu_port: int = 11111
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings() 