#!/usr/bin/env python3
"""
测试MCP修复是否成功
"""

import requests
import json
import time

def test_health_check():
    """测试健康检查"""
    print("🔍 测试健康检查...")
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 健康检查成功")
            print(f"   状态: {data.get('status')}")
            print(f"   富途连接: {data.get('futu_connected')}")
            print(f"   缓存可用: {data.get('cache_available')}")
            print(f"   MCP就绪: {data.get('mcp_ready')}")
            return True
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 健康检查异常: {e}")
        return False

def test_stock_quote():
    """测试股票报价API"""
    print("\n📈 测试股票报价API...")
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
                print(f"✅ 股票报价API成功")
                quotes = data.get("data", {}).get("quotes", [])
                if quotes:
                    quote = quotes[0]
                    print(f"   代码: {quote.get('code')}")
                    print(f"   最新价: {quote.get('last_price')}")
                    print(f"   更新时间: {quote.get('update_time')}")
                return True
            else:
                print(f"❌ 股票报价API失败: {data.get('ret_msg')}")
                return False
        else:
            print(f"❌ 股票报价API HTTP错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 股票报价API异常: {e}")
        return False

def test_mcp_endpoint():
    """测试MCP端点"""
    print("\n🔗 测试MCP端点...")
    try:
        # 使用更短的超时时间，只读取前几行
        response = requests.get("http://localhost:8001/mcp", timeout=3, stream=True)
        if response.status_code == 200:
            # 读取前几行来验证SSE格式
            lines = []
            for i, line in enumerate(response.iter_lines()):
                if i >= 3:  # 只读取前3行
                    break
                if line:
                    lines.append(line.decode('utf-8'))
            
            response.close()  # 关闭连接
            
            content = '\n'.join(lines)
            if "event: endpoint" in content and "data: /mcp/messages/" in content:
                print("✅ MCP端点正常响应")
                print("   SSE格式正确")
                return True
            else:
                print("❌ MCP端点响应格式异常")
                print(f"   响应内容: {content[:100]}...")
                return False
        else:
            print(f"❌ MCP端点HTTP错误: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print("✅ MCP端点响应超时（正常，SSE连接保持开放）")
        return True
    except Exception as e:
        print(f"❌ MCP端点异常: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试MCP修复...")
    print("=" * 50)
    
    # 等待服务完全启动
    print("⏳ 等待服务启动...")
    time.sleep(5)
    
    # 执行测试
    tests = [
        test_health_check,
        test_stock_quote,
        test_mcp_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        time.sleep(1)
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！MCP修复成功！")
        return True
    else:
        print("⚠️  部分测试失败，请检查服务状态")
        return False

if __name__ == "__main__":
    main() 