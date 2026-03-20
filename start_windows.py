#!/usr/bin/env python3
"""
富途 MCP 服务 - Windows 统一启动入口
提供菜单式操作，支持一键启动、停止、重启和状态查看

使用方法:
    python start_windows.py              # 交互式菜单
    python start_windows.py start        # 启动所有服务
    python start_windows.py stop         # 停止所有服务
    python start_windows.py restart      # 重启所有服务
    python start_windows.py status       # 查看状态
    python start_windows.py web          # 仅启动 Web API
    python start_windows.py mcp          # 仅启动 MCP 服务
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

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

from windows_service import (
    WindowsServiceManager, 
    ServiceConfig, 
    ServiceStatus,
    register_default_services,
    get_service_manager
)
from utils.process_manager import get_process_manager


class Colors:
    """终端颜色 (Windows 兼容)"""
    HEADER = '\033[95m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    BLUE = '\033[94m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    CYAN = '\033[96m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    GREEN = '\033[92m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    YELLOW = '\033[93m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    RED = '\033[91m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    BOLD = '\033[1m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    UNDERLINE = '\033[4m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''
    END = '\033[0m' if sys.platform != 'win32' or 'ANSICON' in os.environ else ''


def print_header():
    """打印标题"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.CYAN}  富途 MCP 服务 - Windows 启动器{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}\n")


def print_menu():
    """打印菜单"""
    print(f"{Colors.BOLD}请选择操作:{Colors.END}\n")
    print(f"  {Colors.GREEN}1{Colors.END}. 启动所有服务")
    print(f"  {Colors.GREEN}2{Colors.END}. 停止所有服务")
    print(f"  {Colors.GREEN}3{Colors.END}. 重启所有服务")
    print(f"  {Colors.GREEN}4{Colors.END}. 查看服务状态")
    print(f"  {Colors.GREEN}5{Colors.END}. 启动 Web API (端口8001)")
    print(f"  {Colors.GREEN}6{Colors.END}. 启动 HTTP 备用 (端口8002)")
    print(f"  {Colors.GREEN}7{Colors.END}. 启动 MCP 服务 (端口9001)")
    print(f"  {Colors.GREEN}8{Colors.END}. 健康检查")
    print(f"  {Colors.GREEN}9{Colors.END}. 查看日志")
    print(f"  {Colors.RED}0{Colors.END}. 退出")
    print()


def check_opend_connection() -> bool:
    """检查富途 OpenD 连接"""
    pm = get_process_manager()
    if pm.is_port_in_use(11111):
        print(f"{Colors.GREEN}✓ 富途 OpenD 已连接 (端口 11111){Colors.END}")
        return True
    else:
        print(f"{Colors.YELLOW}⚠ 警告: 富途 OpenD 似乎未启动!{Colors.END}")
        print(f"{Colors.YELLOW}  请先启动 OpenD 并登录账号{Colors.END}")
        return False


def start_all_services(manager: WindowsServiceManager):
    """启动所有服务"""
    print_header()
    print(f"{Colors.BOLD}启动所有服务...{Colors.END}\n")
    
    check_opend_connection()
    print()
    
    # 按依赖顺序启动
    services_order = ["web_api", "mcp_wrapper"]
    
    for service_name in services_order:
        if service_name not in manager.services:
            continue
        
        service = manager.services[service_name]
        print(f"启动 {service.config.description}...")
        
        if manager.start_service(service_name, wait=True):
            print(f"{Colors.GREEN}✓ {service_name} 启动成功 (端口 {service.config.port}){Colors.END}")
        else:
            print(f"{Colors.RED}✗ {service_name} 启动失败{Colors.END}")
            if service.last_error:
                print(f"  错误: {service.last_error}")
    
    print(f"\n{Colors.GREEN}服务启动完成!{Colors.END}")
    print(f"  Web API:    http://localhost:8001")
    print(f"  API 文档:   http://localhost:8001/docs")
    print(f"  MCP 服务:   http://localhost:9001/mcp")
    print()
    input("按 Enter 键继续...")


def stop_all_services(manager: WindowsServiceManager):
    """停止所有服务"""
    print_header()
    print(f"{Colors.BOLD}停止所有服务...{Colors.END}\n")
    
    results = manager.stop_all_services()
    
    for name, success in results.items():
        status = f"{Colors.GREEN}✓{Colors.END}" if success else f"{Colors.RED}✗{Colors.END}"
        print(f"{status} {name}")
    
    print(f"\n{Colors.GREEN}所有服务已停止{Colors.END}")
    input("\n按 Enter 键继续...")


def restart_all_services(manager: WindowsServiceManager):
    """重启所有服务"""
    print_header()
    print(f"{Colors.BOLD}重启所有服务...{Colors.END}\n")
    
    stop_all_services(manager)
    time.sleep(2)
    start_all_services(manager)


def show_status(manager: WindowsServiceManager):
    """显示服务状态"""
    print_header()
    print(f"{Colors.BOLD}服务状态:{Colors.END}\n")
    
    statuses = manager.get_all_services_status()
    
    print(f"{'服务名称':<20} {'状态':<12} {'端口':<8} {'PID':<10} {'运行时间':<15}")
    print("-" * 70)
    
    for name, info in statuses.items():
        status_color = Colors.GREEN if info['status'] == 'running' else Colors.RED
        uptime_str = ""
        if info['uptime'] > 0:
            uptime = int(info['uptime'])
            if uptime < 60:
                uptime_str = f"{uptime}s"
            elif uptime < 3600:
                uptime_str = f"{uptime//60}m {uptime%60}s"
            else:
                uptime_str = f"{uptime//3600}h {(uptime%3600)//60}m"
        
        pid_str = str(info['pid']) if info['pid'] else "-"
        
        print(f"{name:<20} {status_color}{info['status']:<12}{Colors.END} "
              f"{info['port']:<8} {pid_str:<10} {uptime_str:<15}")
    
    print()
    input("按 Enter 键继续...")


def start_single_service(manager: WindowsServiceManager, service_name: str):
    """启动单个服务"""
    print_header()
    
    if service_name not in manager.services:
        print(f"{Colors.RED}服务 {service_name} 未注册{Colors.END}")
        input("\n按 Enter 键继续...")
        return
    
    check_opend_connection()
    print()
    
    service = manager.services[service_name]
    print(f"启动 {service.config.description}...")
    
    if manager.start_service(service_name, wait=True):
        print(f"{Colors.GREEN}✓ 启动成功!{Colors.END}")
        print(f"  地址: http://localhost:{service.config.port}")
    else:
        print(f"{Colors.RED}✗ 启动失败{Colors.END}")
        if service.last_error:
            print(f"  错误: {service.last_error}")
    
    input("\n按 Enter 键继续...")


def health_check(manager: WindowsServiceManager):
    """健康检查"""
    print_header()
    print(f"{Colors.BOLD}健康检查...{Colors.END}\n")
    
    health = manager.health_check()
    
    overall = health['overall']
    color = Colors.GREEN if overall == 'healthy' else Colors.RED
    print(f"整体状态: {color}{overall.upper()}{Colors.END}\n")
    
    print(f"{'服务':<20} {'运行中':<10} {'端口就绪':<10} {'健康':<10}")
    print("-" * 50)
    
    for name, svc_health in health['services'].items():
        running = f"{Colors.GREEN}✓{Colors.END}" if svc_health['running'] else f"{Colors.RED}✗{Colors.END}"
        port = f"{Colors.GREEN}✓{Colors.END}" if svc_health['port_ready'] else f"{Colors.RED}✗{Colors.END}"
        healthy = f"{Colors.GREEN}✓{Colors.END}" if svc_health['healthy'] else f"{Colors.RED}✗{Colors.END}"
        print(f"{name:<20} {running:<10} {port:<10} {healthy:<10}")
    
    print()
    input("按 Enter 键继续...")


def view_logs():
    """查看日志"""
    print_header()
    print(f"{Colors.BOLD}日志文件:{Colors.END}\n")
    
    log_dir = Path("logs")
    if not log_dir.exists():
        print(f"{Colors.YELLOW}日志目录不存在{Colors.END}")
        input("\n按 Enter 键继续...")
        return
    
    log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not log_files:
        print(f"{Colors.YELLOW}未找到日志文件{Colors.END}")
        input("\n按 Enter 键继续...")
        return
    
    print(f"{'序号':<6} {'文件名':<40} {'大小':<10}")
    print("-" * 60)
    
    for i, log_file in enumerate(log_files[:10], 1):
        size = log_file.stat().st_size
        if size < 1024:
            size_str = f"{size}B"
        elif size < 1024 * 1024:
            size_str = f"{size/1024:.1f}KB"
        else:
            size_str = f"{size/(1024*1024):.1f}MB"
        
        print(f"{i:<6} {log_file.name:<40} {size_str:<10}")
    
    print(f"\n{Colors.CYAN}提示: 使用 'tail -f logs/xxx.log' 查看实时日志{Colors.END}")
    input("\n按 Enter 键继续...")


def interactive_mode(manager: WindowsServiceManager):
    """交互模式"""
    while True:
        print_header()
        print_menu()
        
        choice = input("请输入选项 [0-9]: ").strip()
        
        if choice == '1':
            start_all_services(manager)
        elif choice == '2':
            stop_all_services(manager)
        elif choice == '3':
            restart_all_services(manager)
        elif choice == '4':
            show_status(manager)
        elif choice == '5':
            start_single_service(manager, 'web_api')
        elif choice == '6':
            start_single_service(manager, 'web_api_simple')
        elif choice == '7':
            start_single_service(manager, 'mcp_wrapper')
        elif choice == '8':
            health_check(manager)
        elif choice == '9':
            view_logs()
        elif choice == '0':
            print(f"\n{Colors.GREEN}再见!{Colors.END}\n")
            break
        else:
            print(f"{Colors.RED}无效选项{Colors.END}")
            time.sleep(1)


def command_line_mode(args: argparse.Namespace):
    """命令行模式"""
    manager = register_default_services()
    
    if args.command == 'start':
        if args.service:
            for svc in args.service:
                start_single_service(manager, svc)
        else:
            start_all_services(manager)
    
    elif args.command == 'stop':
        if args.service:
            for svc in args.service:
                manager.stop_service(svc)
        else:
            stop_all_services(manager)
    
    elif args.command == 'restart':
        if args.service:
            for svc in args.service:
                manager.restart_service(svc)
        else:
            restart_all_services(manager)
    
    elif args.command == 'status':
        show_status(manager)
    
    elif args.command == 'health':
        health_check(manager)
    
    elif args.command == 'web':
        start_single_service(manager, 'web_api')
    
    elif args.command == 'mcp':
        start_single_service(manager, 'mcp_wrapper')


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='富途 MCP 服务 - Windows 启动器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python start_windows.py              # 交互式菜单
  python start_windows.py start        # 启动所有服务
  python start_windows.py stop         # 停止所有服务
  python start_windows.py restart      # 重启所有服务
  python start_windows.py status       # 查看状态
  python start_windows.py web          # 仅启动 Web API
  python start_windows.py mcp          # 仅启动 MCP 服务
        '''
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        choices=['start', 'stop', 'restart', 'status', 'health', 'web', 'mcp'],
        help='要执行的命令 (默认: 交互式菜单)'
    )
    
    parser.add_argument(
        '--service', '-s',
        nargs='+',
        help='指定要操作的服务名称'
    )
    
    args = parser.parse_args()
    
    # 注册默认服务
    manager = register_default_services()
    
    if args.command:
        # 命令行模式
        command_line_mode(args)
    else:
        # 交互模式
        try:
            interactive_mode(manager)
        except KeyboardInterrupt:
            print(f"\n\n{Colors.GREEN}再见!{Colors.END}\n")


if __name__ == "__main__":
    main()
