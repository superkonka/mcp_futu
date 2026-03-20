"""
Windows 服务管理器
提供 Windows 11 特定的服务管理功能
"""

import os
import sys
import time
import ctypes
import subprocess
import platform
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from utils.process_manager import ProcessManager, get_process_manager
from utils.path_helper import get_path_helper, get_project_root


class ServiceStatus(Enum):
    """服务状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ServiceConfig:
    """服务配置"""
    name: str
    script: str
    port: int
    description: str = ""
    python_executable: Optional[str] = None
    working_dir: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    auto_restart: bool = False
    max_restart_attempts: int = 3
    restart_delay: int = 5


@dataclass
class ServiceInfo:
    """服务信息"""
    config: ServiceConfig
    status: ServiceStatus
    pid: Optional[int] = None
    start_time: Optional[float] = None
    restart_count: int = 0
    last_error: Optional[str] = None


class WindowsServiceManager:
    """
    Windows 服务管理器
    管理富途 MCP 相关服务的启动、停止和监控
    """
    
    def __init__(self):
        self.system = platform.system()
        self.is_admin = self._check_admin()
        self.process_manager = get_process_manager()
        self.path_helper = get_path_helper()
        
        # 服务注册表
        self.services: Dict[str, ServiceInfo] = {}
        
        # 默认配置
        self.project_root = get_project_root()
        self.python_executable = self._find_python_executable()
        
        logger.info(f"Windows 服务管理器初始化")
        logger.info(f"  操作系统: {self.system}")
        logger.info(f"  管理员权限: {self.is_admin}")
        logger.info(f"  Python: {self.python_executable}")
        logger.info(f"  项目根目录: {self.project_root}")
    
    def _check_admin(self) -> bool:
        """检查是否以管理员权限运行"""
        if self.system == "Windows":
            try:
                return ctypes.windll.shell32.IsUserAnAdmin()
            except Exception:
                return False
        else:
            return os.geteuid() == 0 if hasattr(os, 'geteuid') else False
    
    def _find_python_executable(self) -> str:
        """查找 Python 可执行文件"""
        # 优先使用虚拟环境中的 Python
        venv_paths = [
            self.project_root / "venv" / "Scripts" / "python.exe",
            self.project_root / "venv" / "bin" / "python",
            self.project_root / ".venv" / "Scripts" / "python.exe",
            self.project_root / ".venv" / "bin" / "python",
        ]
        
        for path in venv_paths:
            if path.exists():
                return str(path)
        
        # 使用当前 Python
        return sys.executable
    
    def register_service(self, config: ServiceConfig) -> None:
        """注册服务"""
        # 设置默认值
        if not config.python_executable:
            config.python_executable = self.python_executable
        if not config.working_dir:
            config.working_dir = str(self.project_root)
        
        self.services[config.name] = ServiceInfo(
            config=config,
            status=ServiceStatus.STOPPED
        )
        logger.info(f"注册服务: {config.name} (端口 {config.port})")
    
    def unregister_service(self, name: str) -> bool:
        """注销服务"""
        if name not in self.services:
            return False
        
        # 先停止服务
        self.stop_service(name)
        del self.services[name]
        logger.info(f"注销服务: {name}")
        return True
    
    def start_service(self, name: str, wait: bool = True, 
                      timeout: float = 30.0) -> bool:
        """启动服务"""
        if name not in self.services:
            logger.error(f"服务未注册: {name}")
            return False
        
        service = self.services[name]
        config = service.config
        
        # 检查服务状态
        if service.status == ServiceStatus.RUNNING:
            # 检查进程是否真的在运行
            if self._is_service_running(service):
                logger.info(f"服务 {name} 已在运行中 (PID: {service.pid})")
                return True
            else:
                logger.warning(f"服务 {name} 状态为运行但进程不存在，将重启")
        
        # 检查端口占用
        if self.process_manager.is_port_in_use(config.port):
            logger.warning(f"端口 {config.port} 被占用，尝试释放")
            self.process_manager.kill_process_by_port(config.port)
            time.sleep(1)
        
        # 更新状态
        service.status = ServiceStatus.STARTING
        service.last_error = None
        
        try:
            # 构建命令
            script_path = Path(config.working_dir) / config.script
            cmd = [config.python_executable, str(script_path)]
            
            # 环境变量
            env = {**os.environ, **config.env_vars}
            
            logger.info(f"启动服务: {name}")
            logger.debug(f"  命令: {' '.join(cmd)}")
            logger.debug(f"  工作目录: {config.working_dir}")
            
            # 启动进程
            if self.system == "Windows":
                # Windows 使用 CREATE_NEW_PROCESS_GROUP
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                
                process = subprocess.Popen(
                    cmd,
                    cwd=config.working_dir,
                    env=env,
                    creationflags=creationflags,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    cwd=config.working_dir,
                    env=env,
                    start_new_session=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            service.pid = process.pid
            service.start_time = time.time()
            
            logger.info(f"服务 {name} 已启动 (PID: {process.pid})")
            
            if wait:
                if self._wait_for_service_ready(service, timeout):
                    service.status = ServiceStatus.RUNNING
                    service.restart_count = 0
                    return True
                else:
                    service.status = ServiceStatus.ERROR
                    service.last_error = "服务启动超时"
                    return False
            else:
                service.status = ServiceStatus.RUNNING
                return True
                
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.last_error = str(e)
            logger.error(f"启动服务 {name} 失败: {e}")
            return False
    
    def stop_service(self, name: str, timeout: float = 10.0) -> bool:
        """停止服务"""
        if name not in self.services:
            logger.error(f"服务未注册: {name}")
            return False
        
        service = self.services[name]
        
        if service.status == ServiceStatus.STOPPED:
            return True
        
        service.status = ServiceStatus.STOPPING
        
        try:
            if service.pid:
                self.process_manager.kill_process(service.pid, force=False, timeout=timeout)
            
            # 确保端口释放
            if self.process_manager.is_port_in_use(service.config.port):
                self.process_manager.kill_process_by_port(service.config.port, force=True)
            
            service.status = ServiceStatus.STOPPED
            service.pid = None
            service.start_time = None
            
            logger.info(f"服务 {name} 已停止")
            return True
            
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.last_error = str(e)
            logger.error(f"停止服务 {name} 失败: {e}")
            return False
    
    def restart_service(self, name: str, wait: bool = True) -> bool:
        """重启服务"""
        logger.info(f"重启服务: {name}")
        
        if not self.stop_service(name):
            logger.warning(f"停止服务 {name} 失败，强制重启")
        
        time.sleep(2)  # 等待资源释放
        
        return self.start_service(name, wait=wait)
    
    def get_service_status(self, name: str) -> ServiceStatus:
        """获取服务状态"""
        if name not in self.services:
            return ServiceStatus.UNKNOWN
        
        service = self.services[name]
        
        # 检查进程是否真实存在
        if service.status == ServiceStatus.RUNNING:
            if not self._is_service_running(service):
                service.status = ServiceStatus.STOPPED
                service.pid = None
        
        return service.status
    
    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务状态"""
        result = {}
        for name, service in self.services.items():
            # 更新状态
            self.get_service_status(name)
            
            result[name] = {
                "name": name,
                "status": service.status.value,
                "port": service.config.port,
                "pid": service.pid,
                "script": service.config.script,
                "description": service.config.description,
                "uptime": time.time() - service.start_time if service.start_time else 0,
                "restart_count": service.restart_count,
                "last_error": service.last_error
            }
        return result
    
    def _is_service_running(self, service: ServiceInfo) -> bool:
        """检查服务是否真正在运行"""
        if not service.pid:
            # 通过端口检查
            if self.process_manager.is_port_in_use(service.config.port):
                # 查找进程
                proc_info = self.process_manager.find_process_by_port(service.config.port)
                if proc_info:
                    service.pid = proc_info.pid
                    return True
            return False
        
        # 检查进程是否存在
        return self.process_manager.find_process_by_port(service.config.port) is not None
    
    def _wait_for_service_ready(self, service: ServiceInfo, 
                                 timeout: float = 30.0) -> bool:
        """等待服务就绪"""
        config = service.config
        
        # 等待端口就绪
        if not self.process_manager.wait_for_port(config.port, timeout=timeout):
            return False
        
        # 对于 Web 服务，额外检查 HTTP 健康端点
        health_url = f"http://localhost:{config.port}/health"
        if self.process_manager.wait_for_http(health_url, timeout=10):
            return True
        
        # 如果 HTTP 检查失败，但端口是通的，也算成功
        return self.process_manager.is_port_in_use(config.port)
    
    def start_all_services(self, wait: bool = True) -> Dict[str, bool]:
        """启动所有服务"""
        results = {}
        for name in self.services:
            results[name] = self.start_service(name, wait=wait)
        return results
    
    def stop_all_services(self) -> Dict[str, bool]:
        """停止所有服务"""
        results = {}
        for name in self.services:
            results[name] = self.stop_service(name)
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        all_healthy = True
        services_health = {}
        
        for name, service in self.services.items():
            is_running = self._is_service_running(service)
            port_ready = self.process_manager.is_port_in_use(service.config.port)
            
            healthy = is_running and port_ready
            if not healthy:
                all_healthy = False
            
            services_health[name] = {
                "running": is_running,
                "port_ready": port_ready,
                "healthy": healthy,
                "pid": service.pid,
                "port": service.config.port
            }
        
        return {
            "overall": "healthy" if all_healthy else "unhealthy",
            "services": services_health
        }


# 便捷函数
_service_manager = None

def get_service_manager() -> WindowsServiceManager:
    """获取全局服务管理器实例"""
    global _service_manager
    if _service_manager is None:
        _service_manager = WindowsServiceManager()
    return _service_manager


def register_default_services():
    """注册默认服务"""
    manager = get_service_manager()
    
    # 主 Web API 服务
    manager.register_service(ServiceConfig(
        name="web_api",
        script="main_enhanced.py",
        port=8001,
        description="富途 MCP Web API 服务 (MCP + HTTP)",
        env_vars={"PYTHONUNBUFFERED": "1"}
    ))
    
    # HTTP 备用服务
    manager.register_service(ServiceConfig(
        name="web_api_simple",
        script="main_enhanced_simple_alternative.py",
        port=8002,
        description="富途 MCP HTTP 备用服务 (纯 HTTP)",
        env_vars={"PYTHONUNBUFFERED": "1"}
    ))
    
    # MCP 独立服务
    manager.register_service(ServiceConfig(
        name="mcp_wrapper",
        script="mcp_service/main.py",
        port=9001,
        description="MCP 独立包装服务",
        env_vars={
            "PYTHONUNBUFFERED": "1",
            "WEB_API_BASE_URL": "http://localhost:8001",
            "MCP_PORT": "9001"
        }
    ))
    
    return manager
