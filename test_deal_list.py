#!/usr/bin/env python3
"""
测试查询成交记录功能（历史成交和当日成交）
"""

import asyncio
import requests
import json
from datetime import datetime, timedelta


def test_deal_list_api():
    """测试查询成交记录API"""
    base_url = "http://127.0.0.1:8001"
    
    print("🧪 测试查询成交记录功能")
    print("=" * 60)
    
    # 计算时间范围（最近30天）
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    
    # 测试请求数据
    test_requests = [
        {
            "name": "查询当日成交（模拟环境）",
            "endpoint": "/api/trade/deal_list",
            "data": {
                "trd_env": "SIMULATE",
                "acc_id": 0,
                "acc_index": 0,
                "refresh_cache": False,
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": True
                }
            }
        },
        {
            "name": "查询当日特定股票成交",
            "endpoint": "/api/trade/deal_list",
            "data": {
                "code": "HK.00700",  # 腾讯控股
                "trd_env": "SIMULATE",
                "acc_id": 0,
                "refresh_cache": True,
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": False
                }
            }
        },
        {
            "name": "查询当日港股市场成交",
            "endpoint": "/api/trade/deal_list",
            "data": {
                "deal_market": "HK",
                "trd_env": "SIMULATE",
                "acc_id": 0,
                "refresh_cache": False,
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": True
                }
            }
        },
        {
            "name": "查询历史成交（最近30天，真实环境）",
            "endpoint": "/api/trade/history_deal_list",
            "data": {
                "start": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                "end": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                "trd_env": "REAL",
                "acc_id": 0,
                "acc_index": 0,
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": True
                }
            },
            "skip": True  # 默认跳过真实环境测试
        },
        {
            "name": "查询历史特定股票成交",
            "endpoint": "/api/trade/history_deal_list",
            "data": {
                "code": "HK.00700",
                "start": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                "end": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                "trd_env": "REAL",
                "acc_id": 0,
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": False
                }
            },
            "skip": True  # 默认跳过真实环境测试
        },
        {
            "name": "查询历史港股市场成交",
            "endpoint": "/api/trade/history_deal_list",
            "data": {
                "deal_market": "HK",
                "start": (end_time - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),
                "end": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                "trd_env": "REAL",
                "acc_id": 0,
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": True
                }
            },
            "skip": True  # 默认跳过真实环境测试
        },
        {
            "name": "查询当日成交（真实环境）",
            "endpoint": "/api/trade/deal_list", 
            "data": {
                "trd_env": "REAL",
                "acc_id": 0,
                "acc_index": 0,
                "refresh_cache": False,
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": True
                }
            },
            "skip": True  # 默认跳过真实环境测试
        }
    ]
    
    for i, test_case in enumerate(test_requests, 1):
        if test_case.get("skip"):
            print(f"⏭️  跳过测试 {i}: {test_case['name']}")
            continue
            
        print(f"\n📋 测试 {i}: {test_case['name']}")
        print(f"接口端点: {test_case['endpoint']}")
        print(f"请求参数: {json.dumps(test_case['data'], indent=2, ensure_ascii=False)}")
        
        try:
            response = requests.post(
                f"{base_url}{test_case['endpoint']}",
                json=test_case['data'],
                timeout=30  # 增加超时时间，交易接口可能较慢
            )
            
            print(f"HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"返回状态: {result.get('ret_code', 'N/A')}")
                print(f"返回消息: {result.get('ret_msg', 'N/A')}")
                
                if result.get('ret_code') == 0:
                    print("✅ 查询成功!")
                    
                    data = result.get('data', {})
                    deal_list = data.get('deal_list', [])
                    summary = data.get('summary', {})
                    filter_conditions = data.get('filter_conditions', {})
                    
                    print(f"\n📊 成交概览:")
                    print(f"   成交总笔数: {summary.get('成交总笔数', 'N/A')}")
                    print(f"   买入总数量: {summary.get('买入总数量', 'N/A')}")
                    print(f"   卖出总数量: {summary.get('卖出总数量', 'N/A')}")
                    print(f"   买入总金额: {summary.get('买入总金额', 'N/A')}")
                    print(f"   卖出总金额: {summary.get('卖出总金额', 'N/A')}")
                    print(f"   净买入金额: {summary.get('净买入金额', 'N/A')}")
                    print(f"   总手续费: {summary.get('总手续费', 'N/A')}")
                    
                    # 成交分布
                    deal_distribution = summary.get('成交分布', {})
                    if deal_distribution:
                        print(f"\n📈 成交分布:")
                        print(f"   买入成交: {deal_distribution.get('买入成交', 0)}笔")
                        print(f"   卖出成交: {deal_distribution.get('卖出成交', 0)}笔")
                    
                    # 市场分布
                    market_distribution = summary.get('市场分布', {})
                    if market_distribution:
                        print(f"\n🌏 市场分布:")
                        for market, info in market_distribution.items():
                            print(f"   {market}: {info.get('成交笔数', 0)}笔, 数量{info.get('成交数量', 0)}, 金额{info.get('成交金额', 0)}")
                    
                    # 时间分布（仅当日成交有）
                    time_distribution = summary.get('时间分布', {})
                    if time_distribution:
                        print(f"\n⏰ 时间分布:")
                        for hour, info in sorted(time_distribution.items()):
                            print(f"   {hour}: {info.get('成交笔数', 0)}笔, 金额{info.get('成交金额', 0)}")
                    
                    # 前5大成交
                    top_deals = summary.get('前5大成交', [])
                    if top_deals:
                        print(f"\n🏆 前5大成交:")
                        for deal in top_deals:
                            print(f"   {deal.get('代码', '')}: {deal.get('名称', '')}")
                            print(f"     {deal.get('方向', '')} {deal.get('数量', 0)}股 @ {deal.get('价格', 0)}")
                            print(f"     成交金额: {deal.get('成交金额', 0)}, 时间: {deal.get('时间', 'N/A')}")
                    
                    # 过滤条件
                    print(f"\n🔍 过滤条件:")
                    for key, value in filter_conditions.items():
                        print(f"   {key}: {value}")
                    
                    print(f"\n📝 详细信息:")
                    print(f"   成交记录数: {len(deal_list)}")
                    print(f"   数据更新时间: {data.get('update_time', 'N/A')}")
                    print(f"   交易环境: {data.get('trd_env', 'N/A')}")
                    
                    # 显示时间范围（历史成交）
                    if 'date_range' in data:
                        print(f"   查询时间范围: {data.get('date_range', 'N/A')}")
                    
                    # 显示交易日期（当日成交）
                    if 'trade_date' in data:
                        print(f"   交易日期: {data.get('trade_date', 'N/A')}")
                    
                    # 显示前3个成交的详细信息
                    if deal_list and len(deal_list) > 0:
                        print(f"\n📋 前3个成交详情:")
                        for j, deal in enumerate(deal_list[:3], 1):
                            print(f"   成交 {j}:")
                            print(f"     成交号: {deal.get('deal_id', 'N/A')}")
                            print(f"     订单号: {deal.get('order_id', 'N/A')}")
                            print(f"     代码: {deal.get('code', 'N/A')}")
                            print(f"     名称: {deal.get('stock_name', 'N/A')}")
                            print(f"     方向: {deal.get('trd_side', 'N/A')}")
                            print(f"     数量: {deal.get('qty', 'N/A')}")
                            print(f"     价格: {deal.get('price', 'N/A')}")
                            print(f"     成交金额: {deal.get('deal_value', 'N/A')}")
                            print(f"     成交时间: {deal.get('create_time', 'N/A')}")
                            print(f"     成交类型: {deal.get('deal_type', 'N/A')}")
                            print(f"     状态: {deal.get('status', 'N/A')}")
                    
                else:
                    print(f"❌ 查询失败: {result.get('ret_msg', '未知错误')}")
                    
            else:
                print(f"❌ HTTP请求失败: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"错误详情: {error_detail.get('detail', response.text)}")
                except:
                    print(f"错误内容: {response.text}")
                    
        except requests.exceptions.Timeout:
            print("⏰ 请求超时 - 交易接口响应较慢，这可能是正常的")
        except requests.exceptions.ConnectionError:
            print("🔌 连接失败 - 请确保服务已启动 (http://127.0.0.1:8001)")
        except Exception as e:
            print(f"❌ 请求异常: {str(e)}")
    
    print("\n" + "=" * 60)
    print("💡 测试提示:")
    print("1. 确保富途OpenD已启动且支持交易功能")
    print("2. 当日成交：支持模拟和真实环境")
    print("3. 历史成交：仅支持真实环境，不支持模拟环境")
    print("4. 如果返回空成交，说明账户当前时间段没有成交")
    print("5. 真实环境需要有效的交易账户和实际成交记录")
    print("6. 历史成交查询有30秒10次的频率限制")
    print("7. 时间格式：YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH:MM:SS.MS")


def test_api_connectivity():
    """测试API连接性"""
    base_url = "http://127.0.0.1:8001"
    
    print("\n🔍 测试API连接性...")
    
    try:
        # 测试健康检查
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 服务健康检查通过")
        else:
            print(f"⚠️  服务状态异常: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 无法连接到服务: {str(e)}")
        return False
    
    return True


if __name__ == "__main__":
    print("🧪 富途成交记录查询测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 首先测试连接性
    if test_api_connectivity():
        # 然后测试具体功能
        test_deal_list_api()
    else:
        print("❌ 服务连接失败，无法进行功能测试") 