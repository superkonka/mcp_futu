#!/usr/bin/env python3
"""
测试查询持仓列表功能
"""

import asyncio
import requests
import json
from datetime import datetime


def test_position_list_api():
    """测试查询持仓列表API"""
    base_url = "http://127.0.0.1:8001"
    
    print("🧪 测试查询持仓列表功能")
    print("=" * 60)
    
    # 测试请求数据
    test_requests = [
        {
            "name": "查询所有持仓（模拟环境）",
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
            "name": "查询特定股票持仓",
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
            "name": "查询港股市场持仓",
            "data": {
                "position_market": "HK",
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
            "name": "查询盈利持仓（盈亏比例>5%）",
            "data": {
                "pl_ratio_min": 5.0,  # 盈利超过5%
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
            "name": "查询亏损持仓（盈亏比例<-2%）",
            "data": {
                "pl_ratio_max": -2.0,  # 亏损超过2%
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
            "name": "查询盈亏在-5%到10%之间的持仓",
            "data": {
                "pl_ratio_min": -5.0,
                "pl_ratio_max": 10.0,
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
            "name": "真实环境持仓（需要有真实账户）",
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
        print(f"请求参数: {json.dumps(test_case['data'], indent=2, ensure_ascii=False)}")
        
        try:
            response = requests.post(
                f"{base_url}/api/trade/position_list",
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
                    position_list = data.get('position_list', [])
                    summary = data.get('summary', {})
                    filter_conditions = data.get('filter_conditions', {})
                    
                    print(f"\n📊 持仓概览:")
                    print(f"   持仓总数: {summary.get('持仓总数', 'N/A')}")
                    print(f"   总市值: {summary.get('总市值', 'N/A')}")
                    print(f"   总盈亏: {summary.get('总盈亏', 'N/A')}")
                    print(f"   整体盈亏比例: {summary.get('整体盈亏比例', 'N/A')}")
                    
                    # 持仓分布
                    position_distribution = summary.get('持仓分布', {})
                    if position_distribution:
                        print(f"\n📈 持仓分布:")
                        print(f"   盈利持仓: {position_distribution.get('盈利持仓', 0)}只")
                        print(f"   亏损持仓: {position_distribution.get('亏损持仓', 0)}只")
                        print(f"   持平持仓: {position_distribution.get('持平持仓', 0)}只")
                    
                    # 市场分布
                    market_distribution = summary.get('市场分布', {})
                    if market_distribution:
                        print(f"\n🌏 市场分布:")
                        for market, info in market_distribution.items():
                            print(f"   {market}: {info.get('数量', 0)}只股票, 市值{info.get('市值', 0)}, 盈亏{info.get('盈亏', 0)}")
                    
                    # 前5大持仓
                    top_positions = summary.get('前5大持仓', [])
                    if top_positions:
                        print(f"\n🏆 前5大持仓:")
                        for pos in top_positions:
                            print(f"   {pos.get('代码', '')}: {pos.get('名称', '')}")
                            print(f"     市值: {pos.get('市值', 0)}, 盈亏: {pos.get('盈亏', 0)}, 比例: {pos.get('盈亏比例', 'N/A')}")
                    
                    # 过滤条件
                    print(f"\n🔍 过滤条件:")
                    for key, value in filter_conditions.items():
                        print(f"   {key}: {value}")
                    
                    print(f"\n📝 详细信息:")
                    print(f"   持仓记录数: {len(position_list)}")
                    print(f"   数据更新时间: {data.get('update_time', 'N/A')}")
                    print(f"   交易环境: {data.get('trd_env', 'N/A')}")
                    
                    # 显示前3个持仓的详细信息
                    if position_list and len(position_list) > 0:
                        print(f"\n📋 前3个持仓详情:")
                        for j, pos in enumerate(position_list[:3], 1):
                            print(f"   持仓 {j}:")
                            print(f"     代码: {pos.get('code', 'N/A')}")
                            print(f"     名称: {pos.get('stock_name', 'N/A')}")
                            print(f"     持有数量: {pos.get('qty', 'N/A')}")
                            print(f"     可卖数量: {pos.get('can_sell_qty', 'N/A')}")
                            print(f"     市价: {pos.get('nominal_price', 'N/A')}")
                            print(f"     成本价: {pos.get('cost_price', 'N/A')}")
                            print(f"     市值: {pos.get('market_val', 'N/A')}")
                            print(f"     盈亏: {pos.get('pl_val', 'N/A')}")
                            print(f"     盈亏比例: {pos.get('pl_ratio', 'N/A')}")
                            print(f"     持仓状态: {pos.get('position_status', 'N/A')}")
                    
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
    print("2. 模拟环境测试无需真实资金，但需要有模拟持仓")
    print("3. 如果返回空持仓，说明账户当前没有持仓")
    print("4. 真实环境需要有效的交易账户和实际持仓")
    print("5. 盈亏比例过滤：正数表示盈利，负数表示亏损")


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
    print("🧪 富途持仓列表查询测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 首先测试连接性
    if test_api_connectivity():
        # 然后测试具体功能
        test_position_list_api()
    else:
        print("❌ 服务连接失败，无法进行功能测试") 