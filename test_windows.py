#!/usr/bin/env python3
"""
富途 MCP 服务 - Windows 适配测试脚本
全面测试 Windows 11 兼容性

使用方法:
    python test_windows.py              # 运行所有测试
    python test_windows.py --quick      # 快速测试
    python test_windows.py --service    # 仅测试服务
    python test_windows.py --api        # 仅测试 API
"""

import os
import sys
import time
import json
import socket
import platform
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# 确保可以导入本地模块
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from loguru import logger

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    duration: float
    message: str = ""
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class WindowsCompatibilityTester:
    """Windows 兼容性测试器"""
    
    def __init__(self):
        self.system = platform.system()
        self.release = platform.release()
        self.version = platform.version()
        self.machine = platform.machine()
        self.python_version = sys.version
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
    def log_section(self, title: str):
        """打印章节标题"""
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  {title}")
        logger.info("=" * 60)
    
    def run_test(self, name: str, test_func) -> TestResult:
        """运行单个测试"""
        logger.info(f"测试: {name}...")
        start = time.time()
        
        try:
            passed, message, details = test_func()
            duration = time.time() - start
            result = TestResult(name, passed, duration, message, details)
            
            if passed:
                logger.success(f"  ✓ 通过 ({duration:.2f}s)")
            else:
                logger.error(f"  ✗ 失败 ({duration:.2f}s): {message}")
            
            self.results.append(result)
            return result
            
        except Exception as e:
            duration = time.time() - start
            result = TestResult(name, False, duration, str(e))
            logger.error(f"  ✗ 异常 ({duration:.2f}s): {e}")
            self.results.append(result)
            return result
    
    # ========== 系统测试 ==========
    
    def test_system_info(self) -> Tuple[bool, str, Dict]:
        """测试系统信息"""
        info = {
            "system": self.system,
            "release": self.release,
            "version": self.version,
            "machine": self.machine,
            "python": self.python_version.split()[0],
            "platform": platform.platform(),
        }
        
        is_windows = self.system == "Windows"
        is_windows_11 = is_windows and ("11" in self.release or int(self.release.split(".")[-1]) >= 22000)
        
        message = f"{info['platform']}, Python {info['python']}"
        
        return is_windows, message, info
    
    def test_python_version(self) -> Tuple[bool, str, Dict]:
        """测试 Python 版本"""
        version_info = sys.version_info
        passed = version_info.major == 3 and version_info.minor >= 10
        
        details = {
            "major": version_info.major,
            "minor": version_info.minor,
            "micro": version_info.micro,
        }
        
        message = f"Python {version_info.major}.{version_info.minor}.{version_info.micro}"
        if not passed:
            message += " (需要 3.10+)"
        
        return passed, message, details
    
    def test_imports(self) -> Tuple[bool, str, Dict]:
        """测试关键模块导入"""
        required_modules = [
            "fastapi",
            "uvicorn",
            "pydantic",
            "pandas",
            "numpy",
            "psutil",
            "httpx",
            "loguru",
        ]
        
        optional_modules = [
            "talib",
            "redis",
        ]
        
        missing = []
        installed = []
        optional_missing = []
        
        for module in required_modules:
            try:
                __import__(module)
                installed.append(module)
            except ImportError:
                missing.append(module)
        
        for module in optional_modules:
            try:
                __import__(module)
                installed.append(f"{module} (optional)")
            except ImportError:
                optional_missing.append(module)
        
        passed = len(missing) == 0
        message = f"已安装: {len(installed)}, 缺失: {len(missing)}"
        
        details = {
            "installed": installed,
            "missing": missing,
            "optional_missing": optional_missing,
        }
        
        return passed, message, details
    
    # ========== 路径测试 ==========
    
    def test_path_handling(self) -> Tuple[bool, str, Dict]:
        """测试路径处理"""
        try:
            from utils.path_helper import PathHelper, get_data_dir, get_cache_dir, get_log_dir
            
            helper = PathHelper()
            
            # 测试各种路径操作
            test_paths = [
                helper.get_absolute_path("data"),
                helper.get_absolute_path("cache", "test"),
                get_data_dir(),
                get_cache_dir(),
                get_log_dir(),
            ]
            
            # 确保目录可创建
            for path in test_paths:
                helper.ensure_dir(path)
            
            details = {
                "project_root": str(helper.project_root),
                "data_dir": str(get_data_dir()),
                "cache_dir": str(get_cache_dir()),
                "log_dir": str(get_log_dir()),
            }
            
            return True, "路径处理正常", details
            
        except Exception as e:
            return False, str(e), {}
    
    def test_file_operations(self) -> Tuple[bool, str, Dict]:
        """测试文件操作"""
        try:
            test_dir = Path("temp_test")
            test_dir.mkdir(exist_ok=True)
            
            # 创建测试文件
            test_file = test_dir / "test.txt"
            test_content = "Hello Windows 11!"
            test_file.write_text(test_content, encoding='utf-8')
            
            # 读取测试
            read_content = test_file.read_text(encoding='utf-8')
            
            # 清理
            test_file.unlink()
            test_dir.rmdir()
            
            passed = read_content == test_content
            message = f"读写测试 {'通过' if passed else '失败'}"
            
            return passed, message, {"test_file": str(test_file)}
            
        except Exception as e:
            return False, str(e), {}
    
    # ========== 进程管理测试 ==========
    
    def test_process_manager(self) -> Tuple[bool, str, Dict]:
        """测试进程管理模块"""
        try:
            from utils.process_manager import ProcessManager, is_port_in_use
            
            pm = ProcessManager()
            
            # 测试端口检查（使用常见端口）
            port_80 = is_port_in_use(80)
            port_443 = is_port_in_use(443)
            
            # 测试查找进程
            python_procs = pm.find_python_processes()
            
            details = {
                "port_80_in_use": port_80,
                "port_443_in_use": port_443,
                "python_processes_found": len(python_procs),
            }
            
            return True, f"找到 {len(python_procs)} 个 Python 进程", details
            
        except Exception as e:
            return False, str(e), {}
    
    def test_port_operations(self) -> Tuple[bool, str, Dict]:
        """测试端口操作"""
        try:
            from utils.process_manager import get_process_manager
            
            pm = get_process_manager()
            
            # 找一个未使用的端口进行测试
            test_port = 55555
            
            # 检查端口状态
            in_use_before = pm.is_port_in_use(test_port)
            
            # 临时监听端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', test_port))
            sock.listen(1)
            
            # 检查端口状态
            in_use_during = pm.is_port_in_use(test_port)
            
            # 关闭端口
            sock.close()
            time.sleep(0.5)
            
            # 检查端口状态
            in_use_after = pm.is_port_in_use(test_port)
            
            details = {
                "port": test_port,
                "before": in_use_before,
                "during": in_use_during,
                "after": in_use_after,
            }
            
            passed = (not in_use_before) and in_use_during and (not in_use_after)
            message = f"端口 {test_port} 状态变化: 空闲->{in_use_during}->空闲"
            
            return passed, message, details
            
        except Exception as e:
            return False, str(e), {}
    
    # ========== 服务管理测试 ==========
    
    def test_service_manager(self) -> Tuple[bool, str, Dict]:
        """测试服务管理器"""
        try:
            from windows_service import WindowsServiceManager, ServiceConfig
            
            manager = WindowsServiceManager()
            
            # 注册测试服务
            test_service = ServiceConfig(
                name="test_service",
                script="test_script.py",
                port=59999,
                description="测试服务"
            )
            
            manager.register_service(test_service)
            
            # 检查服务注册
            registered = "test_service" in manager.services
            
            # 清理
            manager.unregister_service("test_service")
            
            details = {
                "system": manager.system,
                "is_admin": manager.is_admin,
                "python_executable": manager.python_executable,
                "services_count": len(manager.services),
            }
            
            return registered, f"服务管理器初始化成功", details
            
        except Exception as e:
            return False, str(e), {}
    
    # ========== 网络测试 ==========
    
    def test_network_connectivity(self) -> Tuple[bool, str, Dict]:
        """测试网络连接"""
        try:
            import urllib.request
            import socket
            
            # 检查 localhost 解析
            localhost_ip = socket.getaddrinfo('localhost', None)[0][4][0]
            
            # 检查 127.0.0.1
            results = {
                "localhost_resolves": localhost_ip in ['127.0.0.1', '::1'],
                "localhost_ip": localhost_ip,
            }
            
            return True, f"localhost 解析为 {localhost_ip}", results
            
        except Exception as e:
            return False, str(e), {}
    
    def test_futu_opend_connection(self) -> Tuple[bool, str, Dict]:
        """测试富途 OpenD 连接"""
        try:
            from utils.process_manager import is_port_in_use
            
            connected = is_port_in_use(11111)
            
            if connected:
                # 尝试获取进程信息
                from utils.process_manager import find_process_by_port
                proc = find_process_by_port(11111)
                
                details = {
                    "connected": True,
                    "process": proc.name if proc else "unknown",
                    "pid": proc.pid if proc else None,
                }
                
                return True, "富途 OpenD 已连接", details
            else:
                return True, "富途 OpenD 未运行 (这是正常的，请先启动 OpenD)", {"connected": False}
                
        except Exception as e:
            return False, str(e), {}
    
    # ========== API 测试 ==========
    
    def test_api_endpoints(self) -> Tuple[bool, str, Dict]:
        """测试 API 端点"""
        import urllib.request
        import urllib.error
        
        endpoints = [
            ("http://localhost:8001/health", "Web API"),
            ("http://localhost:8002/health", "HTTP 备用"),
            ("http://localhost:9001/mcp/health", "MCP 服务"),
        ]
        
        results = {}
        any_running = False
        
        for url, name in endpoints:
            try:
                response = urllib.request.urlopen(url, timeout=2)
                results[name] = {
                    "status": response.status,
                    "running": True,
                }
                any_running = True
            except urllib.error.HTTPError as e:
                results[name] = {
                    "status": e.code,
                    "running": e.code < 500,
                }
                any_running = True
            except Exception as e:
                results[name] = {
                    "error": str(e),
                    "running": False,
                }
        
        # 如果没有服务运行，测试通过但提示用户
        if not any_running:
            return True, "没有检测到运行中的服务 (请先启动服务)", results
        
        return True, f"检测到 {sum(1 for r in results.values() if r.get('running'))} 个运行中的服务", results
    
    # ========== 运行所有测试 ==========
    
    def run_all_tests(self, quick: bool = False) -> Dict[str, Any]:
        """运行所有测试"""
        logger.info("")
        logger.info("╔" + "=" * 58 + "╗")
        logger.info("║" + " " * 15 + "Windows 兼容性测试" + " " * 25 + "║")
        logger.info("╚" + "=" * 58 + "╝")
        logger.info("")
        
        # 系统测试
        self.log_section("系统测试")
        self.run_test("系统信息", self.test_system_info)
        self.run_test("Python 版本", self.test_python_version)
        self.run_test("模块导入", self.test_imports)
        
        # 路径测试
        self.log_section("路径测试")
        self.run_test("路径处理", self.test_path_handling)
        self.run_test("文件操作", self.test_file_operations)
        
        # 进程管理测试
        self.log_section("进程管理测试")
        self.run_test("进程管理器", self.test_process_manager)
        self.run_test("端口操作", self.test_port_operations)
        
        # 服务管理测试
        self.log_section("服务管理测试")
        self.run_test("服务管理器", self.test_service_manager)
        
        if not quick:
            # 网络测试
            self.log_section("网络测试")
            self.run_test("网络连接", self.test_network_connectivity)
            self.run_test("富途 OpenD", self.test_futu_opend_connection)
            
            # API 测试
            self.log_section("API 测试")
            self.run_test("API 端点", self.test_api_endpoints)
        
        return self.generate_report()
    
    def generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        duration = time.time() - self.start_time
        
        report = {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "duration": duration,
                "success_rate": (passed / total * 100) if total > 0 else 0,
            },
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "duration": r.duration,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ],
        }
        
        # 打印汇总
        logger.info("")
        logger.info("=" * 60)
        logger.info("  测试汇总")
        logger.info("=" * 60)
        logger.info(f"总计: {total} | 通过: {passed} | 失败: {failed}")
        logger.info(f"成功率: {report['summary']['success_rate']:.1f}%")
        logger.info(f"用时: {duration:.2f}s")
        logger.info("=" * 60)
        
        if failed > 0:
            logger.info("")
            logger.error("失败的测试:")
            for r in self.results:
                if not r.passed:
                    logger.error(f"  - {r.name}: {r.message}")
        
        return report


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Windows 兼容性测试")
    parser.add_argument("--quick", action="store_true", help="快速测试")
    parser.add_argument("--output", "-o", help="输出报告到文件")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    
    args = parser.parse_args()
    
    tester = WindowsCompatibilityTester()
    report = tester.run_all_tests(quick=args.quick)
    
    if args.output:
        output_path = Path(args.output)
        if args.json:
            output_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
        else:
            lines = [
                "# Windows 兼容性测试报告",
                "",
                f"测试时间: {datetime.now().isoformat()}",
                f"总计: {report['summary']['total']}",
                f"通过: {report['summary']['passed']}",
                f"失败: {report['summary']['failed']}",
                f"成功率: {report['summary']['success_rate']:.1f}%",
                f"用时: {report['summary']['duration']:.2f}s",
                "",
                "## 详细结果",
                "",
            ]
            for r in report['results']:
                status = "✓" if r['passed'] else "✗"
                lines.append(f"### {status} {r['name']}")
                lines.append(f"- 状态: {'通过' if r['passed'] else '失败'}")
                lines.append(f"- 用时: {r['duration']:.2f}s")
                if r['message']:
                    lines.append(f"- 消息: {r['message']}")
                if r['details']:
                    lines.append(f"- 详情: {r['details']}")
                lines.append("")
            
            output_path.write_text("\n".join(lines), encoding='utf-8')
        
        logger.info(f"报告已保存到: {output_path}")
    
    # 返回退出码
    if report['summary']['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
