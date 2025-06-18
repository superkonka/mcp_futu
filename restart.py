#!/usr/bin/env python3
"""
富途MCP增强服务 - 快速重启脚本
一键停止已有服务并重新启动
"""

import os
import sys
import time
import subprocess
import psutil
import requests

def kill_existing_services():
    """停止已有的富途服务"""
    print("🔍 检查并停止已有服务...")
    killed = 0
    
    # 查找并停止相关进程
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'main_enhanced.py' in cmdline or 'main_enhanced_simple' in cmdline:
                    print(f"   🔪 停止进程 PID:{proc.info['pid']}")
                    proc.terminate()
                    proc.wait(timeout=3)
                    killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            continue
    
    if killed > 0:
        print(f"   ✅ 已停止 {killed} 个进程")
        time.sleep(1)  # 等待端口释放
    else:
        print("   ✅ 没有发现运行中的服务")
    
    return True

def start_service():
    """启动增强版服务"""
    print("🚀 启动增强版服务...")
    
    try:
        # 后台启动服务
        if os.name == 'nt':  # Windows
            process = subprocess.Popen([sys.executable, 'main_enhanced.py'], 
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Linux/Mac
            process = subprocess.Popen([sys.executable, 'main_enhanced.py'],
                                     stdout=subprocess.DEVNULL, 
                                     stderr=subprocess.DEVNULL)
        
        print(f"   📋 服务进程 PID: {process.pid}")
        
        # 等待服务启动
        print("   ⏳ 等待服务启动...")
        for i in range(10):
            try:
                response = requests.get('http://localhost:8001/health', timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'healthy':
                        print(f"   ✅ 服务启动成功! (耗时 {i+1}s)")
                        return True
            except:
                pass
            time.sleep(1)
        
        print("   ❌ 服务启动超时")
        return False
        
    except Exception as e:
        print(f"   ❌ 启动失败: {e}")
        return False

def main():
    """主函数"""
    print("🔄 富途MCP增强服务 - 快速重启")
    print("=" * 50)
    
    # 1. 停止已有服务
    if not kill_existing_services():
        print("❌ 停止服务失败")
        return
    
    # 2. 启动新服务
    if start_service():
        print("\n🎉 重启成功!")
        print("🌐 服务地址: http://localhost:8001")
        print("📚 API文档: http://localhost:8001/docs")
        print("🔍 健康检查: curl http://localhost:8001/health")
    else:
        print("\n❌ 重启失败")

if __name__ == "__main__":
    main() 