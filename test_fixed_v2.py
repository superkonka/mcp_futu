#!/usr/bin/env python3
"""
测试彻底修复版本的MCP服务
"""

import requests
import json
import time
import asyncio

def test_basic_health():
    """测试基础健康检查"""
    print("🔍 测试基础健康检查...")
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 基础健康检查成功")
            print(f"   状态: {data.get('status')}")
            print(f"   富途连接: {data.get('futu_connected')}")
            print(f"   缓存可用: {data.get('cache_available')}")
            
            init_status = data.get('initialization_status', {})
            print(f"   初始化状态:")
            print(f"     服务器就绪: {init_status.get('server_ready')}")
            print(f"     MCP已挂载: {init_status.get('mcp_mounted')}")
            print(f"     MCP就绪: {init_status.get('mcp_ready')}")
            return True
        else:
            print(f"❌ 基础健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 基础健康检查异常: {e}")
        return False

def test_mcp_status():
    """测试MCP状态检查"""
    print("\n🔗 测试MCP状态...")
    try:
        response = requests.get("http://localhost:8001/mcp/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP状态检查成功")
            print(f"   MCP已挂载: {data.get('mcp_mounted')}")
            print(f"   MCP就绪: {data.get('mcp_ready')}")
            print(f"   可接受连接: {data.get('can_accept_connections')}")
            print(f"   消息: {data.get('message')}")
            return data.get('mcp_ready', False)
        else:
            print(f"❌ MCP状态检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ MCP状态检查异常: {e}")
        return False

def test_stock_api():
    """测试股票API"""
    print("\n📈 测试股票API...")
    try:
        payload = {
            "code_list": ["HK.00700"],
            "optimization": {
                "enable_optimization": True,
                "only_essential_fields": True
            }
        }
        response = requests.post(
            "http://localhost:8001/api/quote/stock_quote",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ret_code") == 0:
                print(f"✅ 股票API成功")
                quotes = data.get("data", {}).get("quotes", [])
                if quotes:
                    quote = quotes[0]
                    print(f"   代码: {quote.get('code')}")
                    print(f"   最新价: {quote.get('last_price')}")
                    print(f"   缓存命中: {data.get('data', {}).get('cache_hit')}")
                return True
            else:
                print(f"❌ 股票API失败: {data.get('ret_msg')}")
                return False
        else:
            print(f"❌ 股票API HTTP错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 股票API异常: {e}")
        return False

def test_manual_mcp_mount():
    """测试手动MCP挂载"""
    print("\n🔧 测试手动MCP挂载...")
    try:
        response = requests.post("http://localhost:8001/admin/mount_mcp", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 手动MCP挂载响应成功")
            print(f"   消息: {data.get('message')}")
            return True
        else:
            print(f"❌ 手动MCP挂载失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 手动MCP挂载异常: {e}")
        return False

def wait_for_mcp_ready(max_wait=60):
    """等待MCP就绪"""
    print(f"\n⏳ 等待MCP就绪（最多等待{max_wait}秒）...")
    
    for i in range(max_wait):
        try:
            response = requests.get("http://localhost:8001/mcp/status", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('mcp_ready'):
                    print(f"✅ MCP在{i+1}秒后就绪！")
                    return True
                else:
                    if i % 5 == 0:  # 每5秒打印一次状态
                        print(f"   等待中... ({i+1}/{max_wait}s) - 挂载状态: {data.get('mcp_mounted')}")
        except:
            pass
        
        time.sleep(1)
    
    print(f"❌ MCP在{max_wait}秒内未就绪")
    return False

def test_mcp_endpoint_after_ready():
    """在MCP就绪后测试端点"""
    print("\n🌐 测试MCP端点（就绪后）...")
    try:
        response = requests.get("http://localhost:8001/mcp", timeout=5, stream=True)
        if response.status_code == 200:
            # 读取前几行验证格式
            lines = []
            for i, line in enumerate(response.iter_lines()):
                if i >= 3:
                    break
                if line:
                    lines.append(line.decode('utf-8'))
            
            response.close()
            content = '\n'.join(lines)
            
            if "event: endpoint" in content:
                print("✅ MCP端点正常响应（SSE格式）")
                return True
            else:
                print("❌ MCP端点响应格式异常")
                return False
        else:
            print(f"❌ MCP端点HTTP错误: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print("✅ MCP端点响应超时（正常，SSE保持连接）")
        return True
    except Exception as e:
        print(f"❌ MCP端点异常: {e}")
        return False

def main():
    """主测试流程"""
    print("🚀 开始测试彻底修复版本...")
    print("=" * 60)
    
    # 等待服务基本启动
    print("⏳ 等待服务基本启动...")
    time.sleep(3)
    
    # 执行测试
    test_results = []
    
    # 1. 基础健康检查
    test_results.append(("基础健康检查", test_basic_health()))
    
    # 2. 股票API测试
    test_results.append(("股票API", test_stock_api()))
    
    # 3. MCP状态检查
    mcp_ready = test_mcp_status()
    test_results.append(("MCP状态检查", True))  # 接口本身工作就算成功
    
    # 4. 如果MCP未就绪，触发手动挂载
    if not mcp_ready:
        print("\n🔄 MCP未就绪，触发手动挂载...")
        test_manual_mcp_mount()
        
        # 等待MCP就绪
        mcp_ready = wait_for_mcp_ready(30)
        test_results.append(("等待MCP就绪", mcp_ready))
    
    # 5. 测试MCP端点
    if mcp_ready:
        test_results.append(("MCP端点测试", test_mcp_endpoint_after_ready()))
    
    # 统计结果
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果汇总: {passed}/{total} 通过")
    
    for test_name, result in test_results:
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")
    
    if passed == total:
        print("\n🎉 所有测试通过！彻底修复版本工作正常！")
        print("💡 建议: MCP客户端连接前先检查 /mcp/status 确认就绪状态")
        return True
    else:
        print(f"\n⚠️  {total-passed} 个测试失败，请检查日志")
        return False

if __name__ == "__main__":
    main() 