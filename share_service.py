#!/usr/bin/env python3
"""
富途 MCP 服务 - 共享管理脚本
帮助你快速配置服务供他人使用
"""

import os
import sys
import socket
import subprocess
import argparse
from pathlib import Path
from typing import Optional, List

# 获取本机 IP
def get_local_ip() -> str:
    """获取本机内网 IP"""
    try:
        # 方法 1: 使用 socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # 方法 2: 使用 hostname
        return socket.gethostbyname(socket.gethostname())

def get_all_ips() -> List[str]:
    """获取所有网卡 IP"""
    ips = []
    try:
        import psutil
        interfaces = psutil.net_if_addrs()
        for interface_name, interface_addresses in interfaces.items():
            for address in interface_addresses:
                if address.family == socket.AF_INET:
                    if address.address != '127.0.0.1':
                        ips.append((interface_name, address.address))
    except ImportError:
        pass
    return ips

def check_firewall(port: int) -> bool:
    """检查防火墙规则"""
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name=Futu MCP'],
            capture_output=True,
            text=True
        )
        return 'Futu MCP' in result.stdout
    except Exception:
        return False

def add_firewall_rule():
    """添加防火墙规则"""
    print("添加 Windows 防火墙规则...")
    try:
        subprocess.run([
            'netsh', 'advfirewall', 'firewall', 'add', 'rule',
            'name=Futu MCP',
            'dir=in',
            'action=allow',
            'protocol=tcp',
            'localport=8001,8002,9001'
        ], check=True)
        print("✓ 防火墙规则已添加")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 添加失败: {e}")
        print("请以管理员身份运行 PowerShell")
        return False

def remove_firewall_rule():
    """删除防火墙规则"""
    print("删除 Windows 防火墙规则...")
    try:
        subprocess.run([
            'netsh', 'advfirewall', 'firewall', 'delete', 'rule',
            'name=Futu MCP'
        ], check=True)
        print("✓ 防火墙规则已删除")
        return True
    except subprocess.CalledProcessError:
        print("规则不存在或删除失败")
        return False

def update_env_file(host: str = "0.0.0.0"):
    """更新 .env 文件"""
    env_path = Path('.env')
    
    if not env_path.exists():
        print("创建 .env 文件...")
        env_content = f"""# 富途 MCP 服务配置
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
HOST={host}
PORT=8001
LOG_LEVEL=INFO
CACHE_ENABLED=true
PYTHONUNBUFFERED=1
"""
        env_path.write_text(env_content, encoding='utf-8')
    else:
        content = env_path.read_text(encoding='utf-8')
        
        # 更新 HOST
        if 'HOST=' in content:
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith('HOST='):
                    new_lines.append(f'HOST={host}')
                else:
                    new_lines.append(line)
            content = '\n'.join(new_lines)
        else:
            content += f'\nHOST={host}\n'
        
        env_path.write_text(content, encoding='utf-8')
    
    print(f"✓ 已更新 HOST={host}")

def check_service_status():
    """检查服务状态"""
    print("\n" + "="*60)
    print("  服务状态检查")
    print("="*60)
    
    # 检查 IP
    local_ip = get_local_ip()
    print(f"\n本机 IP: {local_ip}")
    
    all_ips = get_all_ips()
    if all_ips:
        print("所有网卡:")
        for name, ip in all_ips:
            print(f"  {name}: {ip}")
    
    # 检查端口
    import urllib.request
    ports = {
        8001: 'Web API',
        8002: 'HTTP 备用',
        9001: 'MCP 服务',
        11111: 'OpenD'
    }
    
    print("\n端口状态:")
    for port, name in ports.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            status = '✓ 运行中' if result == 0 else '✗ 未运行'
            print(f"  {name} (port {port}): {status}")
        except Exception as e:
            print(f"  {name} (port {port}): 检查失败 - {e}")
    
    # 检查防火墙
    print("\n防火墙状态:")
    if check_firewall(8001):
        print("  ✓ 防火墙规则已配置")
    else:
        print("  ✗ 防火墙规则未配置")
    
    # 提供访问地址
    print("\n" + "="*60)
    print("  访问地址 (供他人使用)")
    print("="*60)
    print(f"\nHTTP API: http://{local_ip}:8001")
    print(f"MCP 服务: http://{local_ip}:9001/mcp")
    print(f"API 文档: http://{local_ip}:8001/docs")
    
    print("\nCursor/Claude 配置:")
    print(json.dumps({
        "mcpServers": {
            "futu-shared": {
                "url": f"http://{local_ip}:8001/mcp"
            }
        }
    }, indent=2))

def start_sharing():
    """启动共享"""
    print("="*60)
    print("  启动 MCP 服务共享")
    print("="*60)
    
    # 1. 获取 IP
    local_ip = get_local_ip()
    print(f"\n本机 IP: {local_ip}")
    
    # 2. 更新配置
    print("\n更新配置文件...")
    update_env_file("0.0.0.0")  # 监听所有网卡
    
    # 3. 配置防火墙
    print("\n检查防火墙...")
    if not check_firewall(8001):
        add_firewall_rule()
    else:
        print("防火墙规则已存在")
    
    # 4. 显示信息
    print("\n" + "="*60)
    print("  配置完成！")
    print("="*60)
    print(f"\n其他人可以通过以下地址访问：")
    print(f"  HTTP API: http://{local_ip}:8001")
    print(f"  MCP 服务: http://{local_ip}:9001/mcp")
    print(f"  API 文档: http://{local_ip}:8001/docs")
    
    print("\n请确保：")
    print("  1. 你的电脑保持开机")
    print("  2. 服务正在运行 (python start_windows.py)")
    print("  3. 其他人与你在同一网络")
    
    print("\n现在你可以启动服务：")
    print("  python start_windows.py start")

def stop_sharing():
    """停止共享"""
    print("停止共享服务...")
    
    # 恢复本地绑定
    update_env_file("127.0.0.1")
    
    # 可选：删除防火墙规则
    # remove_firewall_rule()
    
    print("✓ 已恢复本地访问模式")

def main():
    parser = argparse.ArgumentParser(description='富途 MCP 服务共享管理')
    parser.add_argument('--start', action='store_true', help='启动共享配置')
    parser.add_argument('--stop', action='store_true', help='停止共享')
    parser.add_argument('--status', action='store_true', help='查看状态')
    parser.add_argument('--firewall', action='store_true', help='仅配置防火墙')
    
    args = parser.parse_args()
    
    if args.start:
        start_sharing()
    elif args.stop:
        stop_sharing()
    elif args.status:
        check_service_status()
    elif args.firewall:
        add_firewall_rule()
    else:
        # 默认显示状态
        check_service_status()

if __name__ == '__main__':
    import json
    main()
