#!/usr/bin/env python3
"""
测试资金流向和资金分布接口
"""

import requests
import json
import sys
from datetime import datetime, timedelta

# 配置
BASE_URL = "http://localhost:8001"
TIMEOUT = 10

def test_capital_flow():
    """测试资金流向接口"""
    print("=" * 60)
    print("🧪 测试资金流向接口")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "name": "腾讯控股 - 实时资金流向",
            "data": {
                "code": "HK.00700",
                "period_type": "INTRADAY"
            }
        },
        {
            "name": "腾讯控股 - 日线资金流向",
            "data": {
                "code": "HK.00700",
                "period_type": "DAY",
                "start": (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                "end": datetime.now().strftime('%Y-%m-%d')
            }
        },
        {
            "name": "阿里巴巴 - 实时资金流向",
            "data": {
                "code": "HK.09988", 
                "period_type": "INTRADAY"
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试 {i}: {test_case['name']}")
        print(f"📤 请求数据: {json.dumps(test_case['data'], indent=2, ensure_ascii=False)}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/quote/capital_flow",
                json=test_case['data'],
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT
            )
            
            print(f"📡 HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 请求成功")
                print(f"📊 返回码: {data.get('ret_code')}")
                print(f"📝 返回消息: {data.get('ret_msg')}")
                
                if data.get('ret_code') == 0 and data.get('data'):
                    result_data = data['data']
                    
                    # 显示基本信息
                    print(f"📈 股票代码: {result_data.get('code')}")
                    print(f"⏰ 周期类型: {result_data.get('period_type')}")
                    print(f"📊 数据条数: {result_data.get('data_count')}")
                    
                    # 显示汇总信息
                    summary = result_data.get('summary', {})
                    if summary:
                        print(f"📋 资金流向汇总:")
                        print(f"   整体趋势: {summary.get('overall_trend')}")
                        print(f"   主力趋势: {summary.get('main_trend')}")
                        print(f"   最新净流入: {summary.get('latest_net_inflow'):,.0f}")
                        print(f"   最新主力流入: {summary.get('latest_main_inflow'):,.0f}")
                        print(f"   最新时间: {summary.get('latest_time')}")
                    
                    # 显示部分详细数据
                    capital_flow = result_data.get('capital_flow', [])
                    if capital_flow:
                        print(f"📈 前3条资金流向数据:")
                        for j, flow in enumerate(capital_flow[:3]):
                            print(f"   [{j+1}] 时间: {flow.get('capital_flow_item_time')}")
                            print(f"       净流入: {flow.get('in_flow', 0):,.0f}")
                            print(f"       主力流入: {flow.get('main_in_flow', 0):,.0f}")
                            print(f"       大单流入: {flow.get('big_in_flow', 0):,.0f}")
                else:
                    print(f"❌ 接口返回错误: {data.get('ret_msg')}")
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"📝 错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"📝 错误响应: {response.text}")
                    
        except requests.exceptions.ConnectionError:
            print(f"❌ 连接失败: 无法连接到 {BASE_URL}")
            print(f"💡 请确保服务器正在运行")
            return False
        except requests.exceptions.Timeout:
            print(f"❌ 请求超时 ({TIMEOUT}秒)")
        except Exception as e:
            print(f"❌ 请求异常: {e}")
    
    return True

def test_capital_distribution():
    """测试资金分布接口"""
    print("\n" + "=" * 60)
    print("🧪 测试资金分布接口")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "name": "腾讯控股 - 资金分布",
            "data": {
                "code": "HK.00700"
            }
        },
        {
            "name": "阿里巴巴 - 资金分布",
            "data": {
                "code": "HK.09988"
            }
        },
        {
            "name": "小米集团 - 资金分布",
            "data": {
                "code": "HK.01810"
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试 {i}: {test_case['name']}")
        print(f"📤 请求数据: {json.dumps(test_case['data'], indent=2, ensure_ascii=False)}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/quote/capital_distribution",
                json=test_case['data'],
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT
            )
            
            print(f"📡 HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 请求成功")
                print(f"📊 返回码: {data.get('ret_code')}")
                print(f"📝 返回消息: {data.get('ret_msg')}")
                
                if data.get('ret_code') == 0 and data.get('data'):
                    result_data = data['data']
                    
                    # 显示基本信息
                    print(f"📈 股票代码: {result_data.get('code')}")
                    print(f"📊 数据条数: {result_data.get('data_count')}")
                    
                    # 显示汇总信息
                    summary = result_data.get('summary', {})
                    if summary:
                        print(f"📋 资金分布汇总:")
                        print(f"   整体趋势: {summary.get('overall_trend')}")
                        print(f"   总净流入: {summary.get('total_net_inflow'):,.0f}")
                        print(f"   大资金趋势: {summary.get('large_funds_trend')}")
                        print(f"   大资金净流入: {summary.get('large_funds_net_inflow'):,.0f}")
                        print(f"   主导资金类型: {summary.get('dominant_fund_type')}")
                        print(f"   主导资金金额: {summary.get('dominant_fund_amount'):,.0f}")
                        print(f"   更新时间: {summary.get('update_time')}")
                        
                        # 显示详细分解
                        breakdown = summary.get('breakdown', {})
                        if breakdown:
                            print(f"📊 资金分解:")
                            print(f"   特大单净流入: {breakdown.get('super_net', 0):,.0f}")
                            print(f"   大单净流入: {breakdown.get('big_net', 0):,.0f}")
                            print(f"   中单净流入: {breakdown.get('mid_net', 0):,.0f}")
                            print(f"   小单净流入: {breakdown.get('small_net', 0):,.0f}")
                    
                    # 显示原始数据
                    capital_distribution = result_data.get('capital_distribution', [])
                    if capital_distribution:
                        dist_data = capital_distribution[0]  # 通常只有一条数据
                        print(f"📈 原始资金分布数据:")
                        print(f"   特大单: 流入{dist_data.get('capital_in_super', 0):,.0f} | 流出{dist_data.get('capital_out_super', 0):,.0f}")
                        print(f"   大单: 流入{dist_data.get('capital_in_big', 0):,.0f} | 流出{dist_data.get('capital_out_big', 0):,.0f}")
                        print(f"   中单: 流入{dist_data.get('capital_in_mid', 0):,.0f} | 流出{dist_data.get('capital_out_mid', 0):,.0f}")
                        print(f"   小单: 流入{dist_data.get('capital_in_small', 0):,.0f} | 流出{dist_data.get('capital_out_small', 0):,.0f}")
                else:
                    print(f"❌ 接口返回错误: {data.get('ret_msg')}")
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"📝 错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"📝 错误响应: {response.text}")
                    
        except requests.exceptions.ConnectionError:
            print(f"❌ 连接失败: 无法连接到 {BASE_URL}")
            print(f"💡 请确保服务器正在运行")
            return False
        except requests.exceptions.Timeout:
            print(f"❌ 请求超时 ({TIMEOUT}秒)")
        except Exception as e:
            print(f"❌ 请求异常: {e}")
    
    return True

def test_health():
    """测试健康检查"""
    print("\n🏥 检查服务健康状态...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 服务健康")
            return True
        else:
            print(f"❌ 服务异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始测试资金相关接口...")
    
    # 首先检查服务健康状态
    if not test_health():
        print("⚠️ 服务不可用，请检查服务是否启动")
        sys.exit(1)
    
    # 测试资金流向接口
    flow_success = test_capital_flow()
    
    # 测试资金分布接口
    distribution_success = test_capital_distribution()
    
    print("\n" + "=" * 60)
    if flow_success and distribution_success:
        print("✅ 所有测试完成")
        print("💡 提示: 可以通过浏览器访问 http://localhost:8001/docs 查看完整API文档")
    else:
        print("❌ 部分测试失败")
        sys.exit(1) 