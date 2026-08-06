from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    app_name: str = "富途 MCP API 服务 (增强版)"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # 富途 OpenD 配置
    futu_host: str = "127.0.0.1"
    futu_port: int = 65123
    futu_pwd_unlock: Optional[str] = None
    
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8002
    log_level: str = "INFO"
    
    # 缓存配置
    cache_enabled: bool = True
    redis_url: str = "redis://localhost:6379"
    sqlite_path: str = "data/futu_cache.db"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
