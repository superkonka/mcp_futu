"""
跨平台路径处理模块
统一处理 Windows、Linux、MacOS 的路径差异
"""

import os
import sys
import platform
from pathlib import Path, PurePath
from typing import Optional, Union
from functools import lru_cache

from loguru import logger


class PathHelper:
    """跨平台路径助手"""
    
    def __init__(self):
        self.system = platform.system()
        self.project_root = self._get_project_root()
        logger.debug(f"路径助手初始化 - 项目根目录: {self.project_root}")
    
    def _get_project_root(self) -> Path:
        """获取项目根目录"""
        # 从当前文件向上查找
        current_file = Path(__file__).resolve()
        # utils/path_helper.py -> 上级目录是项目根目录
        return current_file.parent.parent
    
    def get_absolute_path(self, *parts: str) -> Path:
        """获取基于项目根目录的绝对路径"""
        return self.project_root.joinpath(*parts).resolve()
    
    def ensure_dir(self, path: Union[str, Path]) -> Path:
        """确保目录存在，如果不存在则创建"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def to_safe_path(self, path: Union[str, Path]) -> str:
        """
        将路径转换为当前平台的安全路径
        - Windows: 处理长路径问题 (\\?\ 前缀)
        - Unix: 保持原样
        """
        path = Path(path).resolve()
        
        if self.system == "Windows":
            # Windows 长路径处理
            path_str = str(path)
            if len(path_str) > 240 and not path_str.startswith("\\\\?\\"):
                # 对于非常长的路径，使用扩展长度路径前缀
                if path_str.startswith("\\\\"):
                    # UNC 路径
                    path_str = "\\\\?\\UNC\\" + path_str[2:]
                else:
                    path_str = "\\\\?\\" + path_str
                return path_str
        
        return str(path)
    
    def join(self, *parts: str) -> Path:
        """跨平台路径拼接"""
        return Path(*parts)
    
    def normalize_env_path(self, env_value: Optional[str]) -> Optional[str]:
        """规范化环境变量中的路径"""
        if not env_value:
            return None
        
        # 处理 Windows 路径中的反斜杠和引号
        path = env_value.strip().strip('"').strip("'")
        
        # 统一转换为 Path 对象再转回字符串
        return str(Path(path))
    
    def get_user_data_dir(self) -> Path:
        """获取用户数据目录"""
        if self.system == "Windows":
            app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if app_data:
                return Path(app_data) / "FutuMCP"
        elif self.system == "Darwin":  # macOS
            home = Path.home()
            return home / "Library" / "Application Support" / "FutuMCP"
        
        # Linux 和后备
        home = Path.home()
        return home / ".futu_mcp"
    
    def get_user_log_dir(self) -> Path:
        """获取用户日志目录"""
        if self.system == "Windows":
            return self.get_user_data_dir() / "logs"
        elif self.system == "Darwin":
            return Path.home() / "Library" / "Logs" / "FutuMCP"
        
        return self.get_user_data_dir() / "logs"
    
    def sanitize_filename(self, filename: str) -> str:
        """
        清理文件名中的非法字符
        """
        # 非法字符
        if self.system == "Windows":
            illegal_chars = '<>:"/\\|?*'
        else:
            illegal_chars = '/\0'
        
        result = filename
        for char in illegal_chars:
            result = result.replace(char, '_')
        
        # Windows 保留名称
        if self.system == "Windows":
            reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                       'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                       'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
            name = result.split('.')[0].upper()
            if name in reserved:
                result = f"_{result}"
        
        return result


# 全局实例
_path_helper = None

def get_path_helper() -> PathHelper:
    """获取全局路径助手实例"""
    global _path_helper
    if _path_helper is None:
        _path_helper = PathHelper()
    return _path_helper


# 便捷函数
def get_project_root() -> Path:
    """获取项目根目录"""
    return get_path_helper().project_root

def get_data_dir(subdir: Optional[str] = None) -> Path:
    """获取数据目录"""
    helper = get_path_helper()
    path = helper.get_absolute_path("data")
    if subdir:
        path = path / subdir
    return helper.ensure_dir(path)

def get_cache_dir(subdir: Optional[str] = None) -> Path:
    """获取缓存目录"""
    helper = get_path_helper()
    path = helper.get_absolute_path("cache")
    if subdir:
        path = path / subdir
    return helper.ensure_dir(path)

def get_log_dir() -> Path:
    """获取日志目录"""
    helper = get_path_helper()
    return helper.ensure_dir(helper.get_absolute_path("logs"))

def ensure_dir(path: Union[str, Path]) -> Path:
    """确保目录存在"""
    return get_path_helper().ensure_dir(path)

def join_path(*parts: str) -> Path:
    """跨平台路径拼接"""
    return Path(*parts)

def to_safe_path(path: Union[str, Path]) -> str:
    """转换为安全路径"""
    return get_path_helper().to_safe_path(path)
