#!/usr/bin/env python3
"""
富途MCP增强服务 - 智能统一入口
提供建议和对应的响应，一站式解决所有需求
"""

import os
import sys
import time
import subprocess
import requests
import json
from pathlib import Path

class FutuAssistant:
    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.commands = {
            "1": {"name": "启动服务", "cmd": "python restart.py", "desc": "智能重启富途服务"},
            "2": {"name": "健康检查", "cmd": "self.check_health()", "desc": "检查服务状态和连接"},
            "3": {"name": "测试功能", "cmd": "python test_complete_functionality.py", "desc": "完整功能测试"},
            "4": {"name": "股票报价", "cmd": "self.get_stock_quote()", "desc": "获取实时股票报价"},
            "5": {"name": "技术分析", "cmd": "self.get_technical_analysis()", "desc": "计算技术指标"},
            "6": {"name": "缓存状态", "cmd": "self.check_cache()", "desc": "查看缓存系统状态"},
            "7": {"name": "时间查询", "cmd": "self.get_current_time()", "desc": "获取当前时间和时间上下文"},
            "8": {"name": "API文档", "cmd": "self.open_docs()", "desc": "打开API文档"},
            "9": {"name": "查看日志", "cmd": "self.check_logs()", "desc": "检查服务运行日志"},
            "a": {"name": "故障诊断", "cmd": "self.diagnose()", "desc": "智能故障诊断"},
            "0": {"name": "退出", "cmd": "exit", "desc": "退出助手"}
        }
    
    def show_banner(self):
        """显示欢迎横幅"""
        print("\n" + "="*60)
        print("🚀 富途MCP增强服务 - 智能助手")
        print("🎯 一站式解决所有需求")
        print("="*60)
    
    def show_menu(self):
        """显示主菜单"""
        print("\n📋 功能菜单:")
        print("┌─────┬──────────┬────────────────────────┐")
        print("│ 编号 │   功能   │          描述          │")
        print("├─────┼──────────┼────────────────────────┤")
        for key, value in self.commands.items():
            print(f"│  {key}  │ {value['name']:<8} │ {value['desc']:<22} │")
        print("└─────┴──────────┴────────────────────────┘")
    
    def check_health(self):
        """检查服务健康状态"""
        print("🔍 检查服务健康状态...")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print("✅ 服务状态正常")
                print(f"   📊 富途连接: {'✅' if data.get('futu_connected') else '❌'}")
                print(f"   🗄️  缓存系统: {'✅' if data.get('cache_available') else '❌'}")
                if 'cache_stats' in data:
                    stats = data['cache_stats']
                    print(f"   💾 内存缓存: {stats.get('memory_cache_size', 0)}/{stats.get('memory_max_size', 2000)}")
                    print(f"   🗃️  SQLite记录: {stats.get('sqlite_kline_count', 0)}条K线")
                return True
            else:
                print(f"❌ 服务异常 - HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ 服务未响应: {e}")
            print("💡 建议: 运行 '1' 启动服务")
            return False
    
    def get_stock_quote(self):
        """获取股票报价"""
        print("📈 获取股票报价")
        code = input("请输入股票代码 (如 HK.00700): ").strip()
        if not code:
            code = "HK.00700"  # 默认腾讯
        
        try:
            response = requests.post(
                f"{self.base_url}/api/quote/stock_quote",
                json={"code_list": [code]},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('ret_code') == 0 and data.get('data', {}).get('quotes'):
                    quote = data['data']['quotes'][0]
                    print(f"\n💰 {quote['code']} 报价信息:")
                    print(f"   最新价: {quote.get('last_price', 'N/A')}")
                    print(f"   开盘价: {quote.get('open_price', 'N/A')}")
                    print(f"   最高价: {quote.get('high_price', 'N/A')}")
                    print(f"   最低价: {quote.get('low_price', 'N/A')}")
                    print(f"   成交量: {quote.get('volume', 'N/A')}")
                    print(f"   更新时间: {quote.get('update_time', 'N/A')}")
                else:
                    print(f"❌ 获取报价失败: {data.get('ret_msg', '未知错误')}")
            else:
                print(f"❌ 请求失败 - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 获取报价异常: {e}")
    
    def get_technical_analysis(self):
        """获取技术分析"""
        print("🧮 技术指标分析")
        code = input("请输入股票代码 (如 HK.00700): ").strip()
        if not code:
            code = "HK.00700"
        
        indicators = input("请选择指标 (rsi/macd/all, 默认all): ").strip()
        if not indicators:
            indicators = "all"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/analysis/technical_indicators",
                json={
                    "code": code,
                    "indicators": [indicators],
                    "ktype": "K_DAY"
                },
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('ret_code') == 0:
                    print(f"\n📊 {code} 技术分析结果:")
                    result = data.get('data', {})
                    print(f"   数据点数: {result.get('data_points', 'N/A')}")
                    print(f"   分析周期: {result.get('period', 'N/A')}天")
                    
                    indicators_data = result.get('indicators', {})
                    if indicators_data:
                        for indicator_name, indicator_value in indicators_data.items():
                            if isinstance(indicator_value, dict):
                                print(f"   {indicator_name.upper()}:")
                                for key, value in indicator_value.items():
                                    if isinstance(value, (int, float)):
                                        print(f"     {key}: {value:.4f}")
                                    else:
                                        print(f"     {key}: {value}")
                            else:
                                print(f"   {indicator_name}: {indicator_value}")
                else:
                    print(f"❌ 分析失败: {data.get('ret_msg', '未知错误')}")
            else:
                print(f"❌ 请求失败 - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 技术分析异常: {e}")
    
    def check_cache(self):
        """检查缓存状态"""
        print("🗄️  检查缓存状态...")
        try:
            response = requests.get(f"{self.base_url}/api/cache/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('ret_code') == 0:
                    stats = data.get('data', {}).get('stats', {})
                    print("✅ 缓存系统状态:")
                    print(f"   💾 内存缓存: {stats.get('memory_cache_size', 0)}/{stats.get('memory_max_size', 2000)}")
                    print(f"   🔗 Redis: {'✅ 在线' if stats.get('redis_available') else '❌ 离线'}")
                    print(f"   🗃️  SQLite K线: {stats.get('sqlite_kline_count', 0)}条")
                    print(f"   📊 SQLite 指标: {stats.get('sqlite_indicator_count', 0)}条")
                else:
                    print(f"❌ 获取缓存状态失败: {data.get('ret_msg')}")
            else:
                print(f"❌ 请求失败 - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 检查缓存异常: {e}")
    
    def get_current_time(self):
        """获取当前时间和时间上下文"""
        print("🕒 获取当前时间和时间上下文...")
        try:
            response = requests.get(f"{self.base_url}/api/time/current", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('ret_code') == 0:
                    time_data = data.get('data', {})
                    
                    print("✅ 当前时间信息:")
                    print(f"   📅 当前日期: {time_data.get('current_date')}")
                    print(f"   🕐 当前时间: {time_data.get('current_datetime')}")
                    
                    # 格式化信息
                    formatted = time_data.get('formatted', {})
                    print(f"   🌐 中文格式: {formatted.get('chinese')}")
                    print(f"   📆 星期: {formatted.get('weekday_chinese')}")
                    
                    # 市场信息
                    market = time_data.get('market', {})
                    print(f"\n📈 市场状态:")
                    print(f"   🏢 交易日: {'是' if market.get('is_trading_day') else '否'}")
                    print(f"   🔔 交易时间: {'是' if market.get('is_trading_hours') else '否'}")
                    print(f"   🕘 开市时间: {market.get('market_open_time')}")
                    print(f"   🕘 收市时间: {market.get('market_close_time')}")
                    print(f"   📅 下一交易日: {market.get('next_trading_day')}")
                    
                    # 时间上下文映射
                    contexts = time_data.get('time_contexts', {})
                    print(f"\n🎯 时间上下文映射（用于模糊时间理解）:")
                    print(f"   今天: {contexts.get('今天')}")
                    print(f"   昨天: {contexts.get('昨天')}")
                    print(f"   最近: {contexts.get('最近')} (最近3天)")
                    print(f"   近期: {contexts.get('近期')} (最近7天)")
                    print(f"   这几天: {contexts.get('这几天')} (最近5天)")
                    print(f"   本周: {contexts.get('本周')}")
                    print(f"   本月: {contexts.get('本月')}")
                    
                    # 常用时间区间
                    periods = time_data.get('common_periods', {})
                    print(f"\n📊 常用时间区间:")
                    for period_name, period_data in periods.items():
                        print(f"   {period_name}: {period_data.get('start')} 至 {period_data.get('end')}")
                    
                    # LLM使用建议
                    llm_context = time_data.get('llm_context', {})
                    print(f"\n💡 LLM使用建议:")
                    for example in llm_context.get('usage_examples', []):
                        print(f"   • {example}")
                        
                else:
                    print(f"❌ 获取时间信息失败: {data.get('ret_msg')}")
            else:
                print(f"❌ 请求失败 - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 获取时间信息异常: {e}")
    
    def open_docs(self):
        """打开API文档"""
        print("📚 打开API文档...")
        docs_url = f"{self.base_url}/docs"
        
        try:
            # 尝试在浏览器中打开
            if sys.platform == "darwin":  # macOS
                subprocess.run(["open", docs_url])
            elif sys.platform == "win32":  # Windows
                subprocess.run(["start", docs_url], shell=True)
            else:  # Linux
                subprocess.run(["xdg-open", docs_url])
            
            print(f"✅ API文档已在浏览器中打开: {docs_url}")
        except Exception as e:
            print(f"❌ 无法自动打开浏览器: {e}")
            print(f"💡 请手动访问: {docs_url}")
    
    def check_logs(self):
        """检查服务日志"""
        print("📋 检查服务日志...")
        
        # 查找Python进程
        try:
            import psutil
            found_process = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        if 'main_enhanced.py' in cmdline:
                            print(f"✅ 发现服务进程: PID {proc.info['pid']}")
                            print(f"   命令: {cmdline}")
                            found_process = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not found_process:
                print("❌ 未发现运行中的服务进程")
                print("💡 建议: 运行 '1' 启动服务")
        except ImportError:
            print("⚠️  需要安装psutil: pip install psutil")
    
    def diagnose(self):
        """智能故障诊断"""
        print("🔧 开始智能故障诊断...")
        issues = []
        
        # 检查1: 服务状态
        print("   🔍 检查服务状态...")
        if not self.check_service_basic():
            issues.append("服务未启动或无响应")
        
        # 检查2: 富途OpenD连接
        print("   🔍 检查富途OpenD连接...")
        if not self.check_futu_connection():
            issues.append("富途OpenD连接失败")
        
        # 检查3: 端口占用
        print("   🔍 检查端口状态...")
        if not self.check_port_status():
            issues.append("端口被占用或无法访问")
        
        # 检查4: 依赖库
        print("   🔍 检查依赖库...")
        if not self.check_dependencies():
            issues.append("缺少必要依赖库")
        
        # 诊断结果
        if not issues:
            print("\n✅ 诊断完成 - 系统运行正常")
        else:
            print(f"\n❌ 发现 {len(issues)} 个问题:")
            for i, issue in enumerate(issues, 1):
                print(f"   {i}. {issue}")
            
            print("\n💡 建议解决方案:")
            if "服务未启动或无响应" in issues:
                print("   • 运行 '1' 启动服务")
            if "富途OpenD连接失败" in issues:
                print("   • 启动富途OpenD客户端并登录")
            if "端口被占用或无法访问" in issues:
                print("   • 运行 'python restart.py' 重启服务")
            if "缺少必要依赖库" in issues:
                print("   • 运行 'pip install -r requirements_enhanced.txt'")
    
    def check_service_basic(self):
        """基础服务检查"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            return response.status_code == 200
        except:
            return False
    
    def check_futu_connection(self):
        """检查富途连接"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get('futu_connected', False)
        except:
            pass
        return False
    
    def check_port_status(self):
        """检查端口状态"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 8001))
            sock.close()
            return result == 0
        except:
            return False
    
    def check_dependencies(self):
        """检查依赖库"""
        required_modules = ['fastapi', 'futu', 'pandas', 'numpy']
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                return False
        return True
    
    def run_command(self, choice):
        """执行用户选择的命令"""
        if choice not in self.commands:
            print("❌ 无效选择，请重新输入")
            return True
        
        cmd_info = self.commands[choice]
        print(f"\n🚀 执行: {cmd_info['name']}")
        
        if choice == "0":
            print("👋 感谢使用富途MCP增强服务助手!")
            return False
        elif cmd_info['cmd'].startswith('self.'):
            # 执行内部方法
            eval(cmd_info['cmd'])
        else:
            # 执行系统命令
            try:
                result = subprocess.run(cmd_info['cmd'], shell=True, 
                                      capture_output=False, text=True)
                if result.returncode == 0:
                    print("✅ 命令执行完成")
                else:
                    print(f"⚠️  命令执行完成，返回码: {result.returncode}")
            except Exception as e:
                print(f"❌ 命令执行失败: {e}")
        
        return True
    
    def run(self):
        """主运行循环"""
        self.show_banner()
        
        while True:
            self.show_menu()
            try:
                choice = input("\n请选择功能 (0-9, a): ").strip()
                if not self.run_command(choice):
                    break
                
                input("\n按Enter键继续...")
                print("\n" + "-"*60)
                
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，退出助手")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                input("按Enter键继续...")

def main():
    """主函数"""
    assistant = FutuAssistant()
    assistant.run()

if __name__ == "__main__":
    main() 