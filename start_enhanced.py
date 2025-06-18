#!/usr/bin/env python3
"""
富途MCP增强服务 - 智能启动脚本
功能：
1. 自动检测端口占用
2. 停止已有服务
3. 重新启动增强版服务
4. 验证启动成功
"""

import os
import sys
import time
import signal
import subprocess
import platform
import psutil
import requests
from pathlib import Path

# 配置
TARGET_PORTS = [8001, 8002]  # 需要检查的端口
MAIN_SCRIPT = "main_enhanced.py"
HEALTH_CHECK_URL = "http://localhost:8001/health"
MAX_WAIT_TIME = 10  # 最大等待时间(秒)

class ServiceManager:
    def __init__(self):
        self.system = platform.system()
        self.killed_processes = []
    
    def find_processes_by_port(self, port):
        """查找占用指定端口的进程"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 使用新的API方法
                connections = proc.net_connections()
                for conn in connections:
                    if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == port:
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else '',
                            'process': proc
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return processes
    
    def find_python_processes(self, script_name):
        """查找运行指定脚本的Python进程"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if script_name in cmdline:
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline,
                            'process': proc
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return processes
    
    def kill_process(self, process_info):
        """安全地停止进程"""
        try:
            proc = process_info['process']
            pid = process_info['pid']
            
            print(f"🔪 停止进程 PID:{pid} - {process_info['name']}")
            print(f"   命令: {process_info['cmdline'][:100]}...")
            
            # 尝试优雅停止
            proc.terminate()
            
            # 等待进程结束
            try:
                proc.wait(timeout=3)
                print(f"   ✅ 进程 {pid} 已优雅停止")
                self.killed_processes.append(pid)
                return True
            except psutil.TimeoutExpired:
                # 强制停止
                print(f"   ⚠️  进程 {pid} 未响应，强制停止...")
                proc.kill()
                proc.wait(timeout=2)
                print(f"   ✅ 进程 {pid} 已强制停止")
                self.killed_processes.append(pid)
                return True
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"   ❌ 无法停止进程 {process_info['pid']}: {e}")
            return False
        except Exception as e:
            print(f"   ❌ 停止进程时发生错误: {e}")
            return False
    
    def check_and_kill_services(self):
        """检查并停止已有服务"""
        print("🔍 检查已有服务...")
        
        all_processes = {}  # 使用dict而不是set
        
        # 1. 按端口查找
        for port in TARGET_PORTS:
            print(f"\n📍 检查端口 {port}...")
            processes = self.find_processes_by_port(port)
            if processes:
                for proc_info in processes:
                    all_processes[proc_info['pid']] = proc_info
                    print(f"   发现占用进程: PID:{proc_info['pid']} - {proc_info['name']}")
            else:
                print(f"   ✅ 端口 {port} 空闲")
        
        # 2. 按脚本名查找
        print(f"\n🐍 检查Python进程 ({MAIN_SCRIPT})...")
        processes = self.find_python_processes(MAIN_SCRIPT)
        if processes:
            for proc_info in processes:
                all_processes[proc_info['pid']] = proc_info
                print(f"   发现相关进程: PID:{proc_info['pid']} - {proc_info['cmdline'][:80]}...")
        else:
            print(f"   ✅ 未找到 {MAIN_SCRIPT} 相关进程")
        
        # 3. 停止所有找到的进程
        if all_processes:
            print(f"\n🛑 准备停止 {len(all_processes)} 个进程...")
            success_count = 0
            for pid, proc_info in all_processes.items():
                if self.kill_process(proc_info):
                    success_count += 1
            
            print(f"\n📊 停止结果: {success_count}/{len(all_processes)} 个进程已停止")
            
            # 等待端口释放
            print("\n⏳ 等待端口释放...")
            time.sleep(2)
            
            # 验证端口是否释放
            for port in TARGET_PORTS:
                remaining = self.find_processes_by_port(port)
                if remaining:
                    print(f"   ⚠️  端口 {port} 仍被占用: {len(remaining)} 个进程")
                else:
                    print(f"   ✅ 端口 {port} 已释放")
            
            return success_count > 0
        else:
            print("\n✅ 没有发现需要停止的服务")
            return True
    
    def start_service(self):
        """启动增强版服务"""
        print(f"\n🚀 启动增强版服务 ({MAIN_SCRIPT})...")
        
        # 检查脚本文件是否存在
        if not Path(MAIN_SCRIPT).exists():
            print(f"❌ 错误: 找不到启动脚本 {MAIN_SCRIPT}")
            return False
        
        try:
            # 启动服务（后台运行）
            if self.system == "Windows":
                # Windows
                process = subprocess.Popen(
                    [sys.executable, MAIN_SCRIPT],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Linux/Mac
                process = subprocess.Popen(
                    [sys.executable, MAIN_SCRIPT],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid
                )
            
            print(f"   📋 服务进程 PID: {process.pid}")
            print(f"   🌐 服务地址: http://localhost:8001")
            print(f"   📚 API文档: http://localhost:8001/docs")
            
            return process
            
        except Exception as e:
            print(f"❌ 启动服务失败: {e}")
            return None
    
    def wait_for_service(self):
        """等待服务启动并验证"""
        print(f"\n⏳ 等待服务启动...")
        
        for i in range(MAX_WAIT_TIME):
            try:
                response = requests.get(HEALTH_CHECK_URL, timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'healthy':
                        print(f"   ✅ 服务启动成功! (耗时 {i+1}s)")
                        print(f"   📊 富途连接: {'✅' if data.get('futu_connected') else '❌'}")
                        print(f"   🗄️  缓存系统: {'✅' if data.get('cache_available') else '❌'}")
                        return True
                    else:
                        print(f"   ⚠️  服务状态异常: {data.get('status')}")
                        
            except requests.exceptions.RequestException:
                pass  # 连接失败，继续等待
            
            print(f"   ⏳ 等待中... ({i+1}/{MAX_WAIT_TIME})")
            time.sleep(1)
        
        print(f"   ❌ 服务启动超时 ({MAX_WAIT_TIME}s)")
        return False
    
    def restart_service(self):
        """重启服务的完整流程"""
        print("="*60)
        print("🔄 富途MCP增强服务 - 智能重启")
        print("="*60)
        
        # 1. 停止已有服务
        if not self.check_and_kill_services():
            print("❌ 停止服务失败，退出")
            return False
        
        # 2. 启动新服务
        process = self.start_service()
        if not process:
            return False
        
        # 3. 验证服务启动
        if self.wait_for_service():
            print("\n🎉 服务重启成功!")
            print("="*60)
            print("📋 快速验证命令:")
            print("curl http://localhost:8001/health")
            print("curl http://localhost:8001/api/cache/status")
            print("="*60)
            return True
        else:
            print("\n❌ 服务启动验证失败")
            # 尝试停止刚启动的进程
            try:
                if self.system == "Windows":
                    process.terminate()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                print("   🛑 已停止失败的服务进程")
            except:
                pass
            return False

def main():
    """主函数"""
    try:
        manager = ServiceManager()
        success = manager.restart_service()
        
        if success:
            print("\n🌟 提示: 按 Ctrl+C 可以停止服务")
            print("🌟 日志: 服务将在后台运行，查看终端输出了解状态")
            
            # 可选：保持脚本运行以便监控
            try:
                while True:
                    time.sleep(60)
                    # 每分钟检查一次服务状态
                    try:
                        response = requests.get(HEALTH_CHECK_URL, timeout=5)
                        if response.status_code != 200:
                            print(f"⚠️  {time.strftime('%H:%M:%S')} 服务状态异常")
                    except:
                        print(f"❌ {time.strftime('%H:%M:%S')} 服务无响应")
                        break
                        
            except KeyboardInterrupt:
                print("\n\n🛑 用户终止，正在停止服务...")
                manager.check_and_kill_services()
                print("✅ 服务已停止")
        else:
            print("\n❌ 服务重启失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  操作被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 发生未预期的错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 