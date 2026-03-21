"""
严格模式配置 - 禁用所有模拟数据
确保返回的都是真实数据，避免误判
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class StrictSettings(BaseSettings):
    """严格模式配置 - 禁止模拟数据"""
    
    # 应用基础配置
    app_name: str = "富途 MCP API 服务 (严格模式)"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # 富途 OpenD 配置
    futu_host: str = "127.0.0.1"
    futu_port: int = 11111
    futu_telnet_port: int = 65234
    futu_ws_port: int = 33133
    futu_ws_key: Optional[str] = "2e6972a1716376ab"
    futu_unlock_password: Optional[str] = None
    
    # MCP 服务配置
    mcp_name: str = "futu-mcp-server"
    mcp_version: str = "1.0.0"
    external_mcp_endpoint: Optional[str] = "http://localhost:9001/mcp"
    
    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8001
    log_level: str = "INFO"
    dashboard_base_url: str = "http://localhost:8001"
    dashboard_session_timeout_minutes: int = 120
    
    # ==========================================
    # 严格模式配置 - 关键设置
    # ==========================================
    
    # 禁用模拟数据 - 如果为 True，任何情况下都不返回模拟数据
    disable_mock_data: bool = True
    
    # 禁用缓存 - 强制从 OpenD 获取最新数据
    cache_enabled: bool = False
    
    # 强制真实环境 - 忽略 SIMULATE 环境请求
    force_real_env: bool = True
    
    # 禁用降级处理 - API 失败时直接报错
    disable_fallback: bool = True
    
    # 数据新鲜度检查 - 拒绝过期数据 (秒)
    max_data_age_seconds: int = 300  # 5分钟
    
    # 强制数据验证 - 检查数据真实性标记
    strict_data_validation: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# 全局配置实例
strict_settings = StrictSettings()


def validate_real_data(data: dict, source: str = "unknown") -> dict:
    """
    验证数据是否为真实数据
    如果检测到模拟数据标记，抛出异常
    """
    if not strict_settings.disable_mock_data:
        return data
    
    # 检查模拟数据标记
    mock_indicators = [
        "_mock", "mock_", "is_mock", "simulated", 
        "test_data", "dummy", "fake"
    ]
    
    data_str = str(data).lower()
    for indicator in mock_indicators:
        if indicator in data_str:
            raise ValueError(
                f"检测到模拟数据标记 '{indicator}' 来自 {source}. "
                f"严格模式禁止返回模拟数据。"
            )
    
    return data


def ensure_real_environment(trd_env: str) -> str:
    """
    确保使用真实环境
    如果 force_real_env 为 True，强制返回 REAL
    """
    if strict_settings.force_real_env and trd_env.upper() == "SIMULATE":
        return "REAL"
    return trd_env
