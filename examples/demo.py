#!/usr/bin/env python3
"""
富途 MCP API 服务使用示例

本示例展示如何调用富途行情API的各个接口
"""

import asyncio
import httpx
import json
from typing import Dict, Any


# API 基础配置
API_BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


async def call_api(endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """调用API接口的通用方法"""
    url = f"{API_BASE_URL}{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=HEADERS)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            print(f"请求错误: {e}")
            return {"error": str(e)}
        except httpx.HTTPStatusError as e:
            print(f"HTTP错误: {e.response.status_code}")
            return {"error": f"HTTP {e.response.status_code}"}


async def demo_stock_quote():
    """演示获取股票报价"""
    print("\n=== 股票报价示例 ===")
    
    # 获取腾讯(HK.00700)和苹果(US.AAPL)的报价
    request_data = {
        "code_list": ["HK.00700", "US.AAPL"]
    }
    
    result = await call_api("/quote/stock_quote", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def demo_history_kline():
    """演示获取历史K线"""
    print("\n=== 历史K线示例 ===")
    
    # 获取腾讯最近10条日K线（智能获取最新数据，无需指定时间）
    request_data = {
        "code": "HK.00700",
        "ktype": "K_DAY",
        "autype": "qfq",
        "max_count": 10,  # 系统会自动计算时间范围获取最近10条数据
        "optimization": {
            "enable_optimization": True,
            "only_essential_fields": True  # 只返回核心字段
        }
    }
    
    result = await call_api("/quote/history_kline", request_data)
    print(f"智能获取最近数据请求: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # 演示指定时间范围的K线获取
    print("\n--- 指定时间范围示例 ---")
    specific_request = {
        "code": "HK.00700",
        "start": "2025-06-01",
        "end": "2025-06-15",
        "ktype": "K_DAY",
        "autype": "qfq",
        "optimization": {
            "enable_optimization": True,
            "custom_fields": ["time_key", "close", "change_rate", "volume"]
        }
    }
    
    specific_result = await call_api("/quote/history_kline", specific_request)
    print(f"指定时间范围请求: {json.dumps(specific_request, indent=2)}")
    print(f"指定时间范围响应: {json.dumps(specific_result, indent=2, ensure_ascii=False)}")


async def demo_current_kline():
    """演示获取当前K线"""
    print("\n=== 当前K线示例 ===")
    
    # 获取腾讯最近20个交易日的日K线
    request_data = {
        "code": "HK.00700",
        "num": 20,
        "ktype": "K_DAY",
        "autype": "qfq"
    }
    
    result = await call_api("/quote/current_kline", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def demo_market_snapshot():
    """演示获取市场快照"""
    print("\n=== 市场快照示例 ===")
    
    # 获取多只港股的市场快照
    request_data = {
        "code_list": ["HK.00700", "HK.09988", "HK.03690"]
    }
    
    result = await call_api("/quote/market_snapshot", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def demo_stock_basicinfo():
    """演示获取股票基本信息"""
    print("\n=== 股票基本信息示例 ===")
    
    # 推荐使用优化配置，避免token超出
    request_data = {
        "market": "HK",
        "stock_type": "STOCK",
        "max_count": 20,  # 限制返回数量，避免token超出
        "optimization": {
            "enable_optimization": True,
            "only_essential_fields": True,  # 只返回核心字段
            "remove_meaningless_values": True  # 移除无意义值
        }
    }
    
    result = await call_api("/quote/stock_basicinfo", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # 演示极简模式 - 只获取代码和名称
    print("\n--- 极简模式示例 ---")
    minimal_request = {
        "market": "HK",
        "stock_type": "STOCK",
        "max_count": 10,
        "optimization": {
            "enable_optimization": True,
            "custom_fields": ["code", "name"]  # 自定义字段
        }
    }
    
    minimal_result = await call_api("/quote/stock_basicinfo", minimal_request)
    print(f"极简模式请求参数: {json.dumps(minimal_request, indent=2)}")
    print(f"极简模式响应结果: {json.dumps(minimal_result, indent=2, ensure_ascii=False)}")


async def demo_order_book():
    """演示获取摆盘数据"""
    print("\n=== 摆盘数据示例 ===")
    
    # 获取腾讯的买卖盘口数据
    request_data = {
        "code": "HK.00700",
        "num": 10
    }
    
    result = await call_api("/quote/order_book", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def demo_rt_ticker():
    """演示获取逐笔数据"""
    print("\n=== 逐笔数据示例 ===")
    
    # 获取腾讯的最近逐笔成交数据
    request_data = {
        "code": "HK.00700",
        "num": 20
    }
    
    result = await call_api("/quote/rt_ticker", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def demo_rt_data():
    """演示获取分时数据"""
    print("\n=== 分时数据示例 ===")
    
    # 获取腾讯的分时数据
    request_data = {
        "code": "HK.00700"
    }
    
    result = await call_api("/quote/rt_data", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def demo_trading_days():
    """演示获取交易日"""
    print("\n=== 交易日示例 ===")
    
    # 获取港股2024年12月的交易日
    request_data = {
        "market": "HK",
        "start": "2024-12-01",
        "end": "2024-12-31"
    }
    
    result = await call_api("/quote/trading_days", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def demo_subscribe():
    """演示订阅行情数据"""
    print("\n=== 订阅行情示例 ===")
    
    # 订阅腾讯的报价和K线数据
    request_data = {
        "code_list": ["HK.00700"],
        "subtype_list": ["QUOTE", "K_DAY"]
    }
    
    result = await call_api("/quote/subscribe", request_data)
    print(f"请求参数: {json.dumps(request_data, indent=2)}")
    print(f"响应结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


async def check_service_health():
    """检查服务健康状态"""
    print("\n=== 服务健康检查 ===")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            response.raise_for_status()
            result = response.json()
            print(f"服务状态: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result.get("futu_connected", False)
        except Exception as e:
            print(f"健康检查失败: {e}")
            return False


async def main():
    """主函数 - 运行所有演示"""
    print("富途 MCP API 服务使用示例")
    print("=" * 50)
    
    # 首先检查服务状态
    if not await check_service_health():
        print("\n❌ 服务未正常运行或富途OpenD未连接，请检查：")
        print("1. 确保富途OpenD客户端已启动")
        print("2. 确保API服务已启动 (python main.py)")
        print("3. 检查网络连接")
        return
    
    print("\n✅ 服务运行正常，开始演示...")
    
    # 运行各种演示
    demos = [
        demo_stock_quote,           # 股票报价
        demo_current_kline,         # 当前K线  
        demo_market_snapshot,       # 市场快照
        demo_order_book,           # 摆盘数据
        demo_trading_days,         # 交易日
        demo_subscribe,            # 订阅行情
        # demo_history_kline,      # 历史K线(数据量大，可选)
        # demo_stock_basicinfo,    # 股票基本信息(数据量大，可选)
        # demo_rt_ticker,          # 逐笔数据(需要订阅，可选)
        # demo_rt_data,            # 分时数据(需要订阅，可选)
    ]
    
    for demo in demos:
        try:
            await demo()
            await asyncio.sleep(1)  # 避免请求过于频繁
        except Exception as e:
            print(f"\n❌ 演示 {demo.__name__} 失败: {e}")
    
    print("\n🎉 演示完成！")
    print("\n💡 提示:")
    print("1. 某些接口(如逐笔、分时)需要先订阅才能获取数据")
    print("2. 历史K线和股票列表接口返回数据量较大，示例中已注释")
    print("3. 请确保有相应市场的行情权限")
    print("4. API文档地址: http://localhost:8000/docs")
    print("5. MCP端点地址: http://localhost:8000/mcp")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main()) 