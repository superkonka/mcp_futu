"""
跨平台进程管理模块
支持 Windows、Linux、MacOS
"""

import os
import sys
import time
import socket
import signal
import subprocess
import platform
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from loguru import logger


@dataclass
class ProcessInfo:
    """进程信息"""
    pid: int
    name: str
    cmdline: List[str]
    port: Optional[int] = None
    create_time: Optional[float] = None


class ProcessManager:
    """跨平台进程管理器"""
    
    def __init__(self):
        self.system = platform.system()
        logger.debug(f"进程管理器初始化 - 操作系统: {self.system}")
    
    def is_port_in_use(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                return result == 0
        except Exception as e:
            logger.error(f"检查端口 {port} 失败: {e}")
            return False
    
    def find_process_by_port(self, port: int) -> Optional[ProcessInfo]:
        """根据端口查找进程"""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil 未安装，无法查找进程")
            return None
        
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    try:
                        proc = psutil.Process(conn.pid)
                        return ProcessInfo(
                            pid=conn.pid,
                            name=proc.name(),
                            cmdline=proc.cmdline(),
                            port=port,
                            create_time=proc.create_time()
                        )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except Exception as e:
            logger.error(f"查找端口 {port} 的进程失败: {e}")
        
        return None
    
    def find_python_processes(self, script_name: Optional[str] = None) -> List[ProcessInfo]:
        """查找 Python 进程"""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil 未安装，无法查找进程")
            return []
        
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    pinfo = proc.info
                    if not pinfo['name']:
                        continue
                    
                    name = pinfo['name'].lower()
                    # 匹配各种 Python 可执行文件名
                    if any(x in name for x in ['python', 'python3', 'python.exe', 'pythonw.exe']):
                        cmdline = pinfo['cmdline'] if pinfo['cmdline'] else []
                        cmd_str = ' '.join(cmdline)
                        
                        # 如果指定了脚本名，进行过滤
                        if script_name and script_name not in cmd_str:
                            continue
                        
                        processes.append(ProcessInfo(
                            pid=pinfo['pid'],
                            name=pinfo['name'],
                            cmdline=cmdline,
                            create_time=pinfo.get('create_time')
                        ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"查找 Python 进程失败: {e}")
        
        return processes
    
    def kill_process(self, pid: int, force: bool = False, timeout: float = 3.0) -> bool:
        """终止进程"""
        if not PSUTIL_AVAILABLE:
            # 使用系统命令作为后备
            return self._kill_process_system(pid, force)
        
        try:
            proc = psutil.Process(pid)
            
            if self.system == "Windows":
                # Windows 上使用 terminate()
                proc.terminate()
            else:
                # Unix 系统尝试 SIGTERM
                proc.terminate()
            
            # 等待进程终止
            try:
                proc.wait(timeout=timeout)
                logger.info(f"进程 {pid} 已终止")
                return True
            except psutil.TimeoutExpired:
                if force:
                    logger.warning(f"进程 {pid} 未响应，强制终止")
                    proc.kill()
                    return True
                else:
                    logger.warning(f"进程 {pid} 终止超时")
                    return False
                    
        except psutil.NoSuchProcess:
            logger.debug(f"进程 {pid} 不存在")
            return True
        except Exception as e:
            logger.error(f"终止进程 {pid} 失败: {e}")
            return self._kill_process_system(pid, force)
    
    def _kill_process_system(self, pid: int, force: bool = False) -> bool:
        """使用系统命令终止进程"""
        try:
            if self.system == "Windows":
                cmd = f"taskkill /PID {pid} /T /F" if force else f"taskkill /PID {pid} /T"
            else:
                sig = "-9" if force else "-15"
                cmd = f"kill {sig} {pid}"
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"系统命令终止进程 {pid} 失败: {e}")
            return False
    
    def kill_process_by_port(self, port: int, force: bool = False) -> bool:
        """终止占用指定端口的进程"""
        proc_info = self.find_process_by_port(port)
        if not proc_info:
            logger.debug(f"端口 {port} 未被占用")
            return True
        
        logger.info(f"终止占用端口 {port} 的进程 (PID: {proc_info.pid})")
        return self.kill_process(proc_info.pid, force=force)
    
    def kill_python_processes(self, script_names: Optional[List[str]] = None, 
                              exclude_current: bool = True) -> int:
        """终止 Python 进程"""
        current_pid = os.getpid() if exclude_current else None
        processes = self.find_python_processes()
        
        killed = 0
        for proc in processes:
            if proc.pid == current_pid:
                continue
            
            # 如果指定了脚本名，进行过滤
            if script_names:
                cmd_str = ' '.join(proc.cmdline)
                if not any(name in cmd_str for name in script_names):
                    continue
            
            if self.kill_process(proc.pid):
                killed += 1
        
        return killed
    
    def start_process(self, cmd: List[str], 
                      background: bool = False,
                      cwd: Optional[str] = None,
                      env: Optional[Dict[str, str]] = None,
                      shell: bool = False) -> subprocess.Popen:
        """启动进程"""
        kwargs = {
            'cwd': cwd,
            'env': {**os.environ, **env} if env else os.environ,
            'shell': shell,
        }
        
        if self.system == "Windows":
            # Windows 特定配置
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            if background:
                kwargs['creationflags'] |= subprocess.CREATE_NO_WINDOW
                kwargs['stdin'] = subprocess.DEVNULL
                kwargs['stdout'] = subprocess.DEVNULL
                kwargs['stderr'] = subprocess.DEVNULL
        else:
            # Unix 配置
            if background:
                kwargs['stdin'] = subprocess.DEVNULL
                kwargs['stdout'] = subprocess.DEVNULL
                kwargs['stderr'] = subprocess.DEVNULL
                kwargs['start_new_session'] = True
        
        return subprocess.Popen(cmd, **kwargs)
    
    def wait_for_port(self, port: int, timeout: float = 30.0, 
                      interval: float = 1.0) -> bool:
        """等待端口就绪"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_port_in_use(port):
                logger.info(f"端口 {port} 已就绪")
                return True
            time.sleep(interval)
            logger.debug(f"等待端口 {port}... ({time.time() - start_time:.1f}s)")
        
        logger.error(f"等待端口 {port} 超时 ({timeout}s)")
        return False
    
    def wait_for_http(self, url: str, timeout: float = 30.0, 
                      interval: float = 1.0) -> bool:
        """等待 HTTP 服务就绪"""
        import urllib.request
        import urllib.error
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = urllib.request.urlopen(url, timeout=2)
                if response.status == 200:
                    logger.info(f"HTTP 服务已就绪: {url}")
                    return True
            except urllib.error.HTTPError as e:
                if e.code in [200, 307, 401, 403]:  # 这些状态码表示服务已启动
                    logger.info(f"HTTP 服务已就绪: {url} (状态: {e.code})")
                    return True
            except Exception:
                pass
            
            time.sleep(interval)
            logger.debug(f"等待 HTTP 服务 {url}... ({time.time() - start_time:.1f}s)")
        
        logger.error(f"等待 HTTP 服务 {url} 超时 ({timeout}s)")
        return False


# 便捷函数
_process_manager = None

def get_process_manager() -> ProcessManager:
    """获取全局进程管理器实例"""
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager

def kill_process_by_port(port: int, force: bool = False) -> bool:
    """终止占用指定端口的进程"""
    return get_process_manager().kill_process_by_port(port, force)

def find_process_by_port(port: int) -> Optional[ProcessInfo]:
    """根据端口查找进程"""
    return get_process_manager().find_process_by_port(port)

def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用"""
    return get_process_manager().is_port_in_use(port)

def wait_for_port(port: int, timeout: float = 30.0) -> bool:
    """等待端口就绪"""
    return get_process_manager().wait_for_port(port, timeout)
