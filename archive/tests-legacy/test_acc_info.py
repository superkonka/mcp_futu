#!/usr/bin/env python3
"""
测试查询账户资金功能
"""

import asyncio
import requests
import json
from datetime import datetime


def test_acc_info_api():
    """测试查询账户资金API"""
    base_url = "http://127.0.0.1:8001"
    
    print("🧪 测试查询账户资金功能")
    print("=" * 60)
    
    # 测试请求数据
    test_requests = [
        {
            "name": "模拟环境港币账户",
            "data": {
                "trd_env": "SIMULATE",
                "acc_id": 0,
                "acc_index": 0,
                "refresh_cache": False,
                "currency": "HKD",
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": True
                }
            }
        },
        {
            "name": "模拟环境美元账户",
            "data": {
                "trd_env": "SIMULATE",
                "acc_id": 0,
                "acc_index": 0,
                "refresh_cache": True,
                "currency": "USD",
                "optimization": {
                    "enable_optimization": True,
                    "only_essential_fields": False
                }
            }
        },
        {
            "name": "真实环境账户（需要有真实账户）",
            "data": {
                "trd_env": "REAL",
                "acc_id": 0,
                "acc_index": 0,
                "refresh_cache": False,
                "currency": "HKD",
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
                f"{base_url}/api/trade/acc_info",
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
                    account_info = data.get('account_info', {})
                    summary = data.get('summary', {})
                    currency_distribution = data.get('currency_distribution', {})
                    
                    print("\n💰 账户资金概览:")
                    print(f"   总资产净值: {summary.get('总资产净值', 'N/A')}")
                    print(f"   可用资金: {summary.get('可用资金', 'N/A')}")
                    print(f"   现金购买力: {summary.get('现金购买力', 'N/A')}")
                    print(f"   证券市值: {summary.get('证券市值', 'N/A')}")
                    print(f"   冻结资金: {summary.get('冻结资金', 'N/A')}")
                    
                    if currency_distribution:
                        print("\n💱 货币分布:")
                        for currency, info in currency_distribution.items():
                            print(f"   {currency}:")
                            print(f"     现金: {info.get('现金', 'N/A')}")
                            print(f"     可用余额: {info.get('可用余额', 'N/A')}")
                            print(f"     购买力: {info.get('购买力', 'N/A')}")
                    
                    print(f"\n📊 详细字段数: {len(account_info)}")
                    print(f"   数据更新时间: {data.get('update_time', 'N/A')}")
                    print(f"   交易环境: {data.get('trd_env', 'N/A')}")
                    print(f"   计价货币: {data.get('currency', 'N/A')}")
                    
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
    print("2. 模拟环境测试无需真实资金")
    print("3. 如果测试失败，请检查OpenD连接状态")
    print("4. 真实环境需要有效的交易账户")


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
    print("🧪 富途账户资金查询测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 首先测试连接性
    if test_api_connectivity():
        # 然后测试具体功能
        test_acc_info_api()
    else:
        print("❌ 服务连接失败，无法进行功能测试") 