#!/usr/bin/env python3
"""
测试复权因子接口
测试获取股票复权因子数据的功能
"""

import asyncio
import json
import aiohttp
from typing import Dict, Any
from datetime import datetime


class RehabTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url

    async def test_health_check(self) -> bool:
        """测试服务健康状态"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    data = await response.json()
                    print("🏥 服务健康检查:")
                    print(f"   状态: {data.get('status', 'unknown')}")
                    print(f"   富途连接: {data.get('futu_connected', False)}")
                    print(f"   缓存可用: {data.get('cache_available', False)}")
                    return data.get("status") == "healthy"
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
            return False

    async def test_rehab(self, code: str) -> Dict[str, Any]:
        """测试复权因子接口"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "code": code,
                    "optimization": {
                        "enable_optimization": True,
                        "only_essential_fields": True,
                        "remove_meaningless_values": True
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/api/quote/rehab",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    return data
                    
        except Exception as e:
            print(f"❌ 测试复权因子失败: {e}")
            return {"ret_code": -1, "ret_msg": str(e), "data": None}

    def print_rehab_data(self, data: Dict[str, Any], code: str):
        """打印复权因子数据"""
        print(f"\n📊 {code} 复权因子数据:")
        print("=" * 80)
        
        if data.get("ret_code") != 0:
            print(f"❌ 获取失败: {data.get('ret_msg', '未知错误')}")
            return
        
        result_data = data.get("data", {})
        rehab_data = result_data.get("rehab_data", [])
        summary = result_data.get("summary", {})
        
        # 打印汇总信息
        print(f"📈 汇总信息:")
        print(f"   总记录数: {summary.get('total_actions', 0)}")
        print(f"   最新行为日期: {summary.get('latest_action_date', 'N/A')}")
        print(f"   最新行为类型: {summary.get('latest_action_type', 'N/A')}")
        print(f"   最新前复权因子A: {summary.get('latest_forward_factor_a', 'N/A')}")
        print(f"   最新前复权因子B: {summary.get('latest_forward_factor_b', 'N/A')}")
        print(f"   最新后复权因子A: {summary.get('latest_backward_factor_a', 'N/A')}")
        print(f"   最新后复权因子B: {summary.get('latest_backward_factor_b', 'N/A')}")
        
        # 打印行为分类统计
        action_breakdown = summary.get('action_breakdown', {})
        print(f"\n📋 公司行为统计:")
        for action_type, count in action_breakdown.items():
            if count > 0:
                print(f"   {action_type}: {count}次")
        
        # 打印详细记录（最近5条）
        if rehab_data:
            print(f"\n📝 详细记录 (最新{min(5, len(rehab_data))}条):")
            for i, record in enumerate(rehab_data[-5:], 1):
                print(f"\n   记录 {i}:")
                print(f"     除权日期: {record.get('ex_div_date', 'N/A')}")
                
                # 显示具体行为
                actions = []
                if record.get('per_cash_div', 0) > 0:
                    actions.append(f"派息 {record.get('per_cash_div', 0)}")
                if record.get('per_share_div_ratio', 0) > 0:
                    actions.append(f"送股比例 {record.get('per_share_div_ratio', 0)}")
                if record.get('per_share_trans_ratio', 0) > 0:
                    actions.append(f"转增比例 {record.get('per_share_trans_ratio', 0)}")
                if record.get('allotment_ratio', 0) > 0:
                    actions.append(f"配股比例 {record.get('allotment_ratio', 0)} @{record.get('allotment_price', 0)}")
                if record.get('stk_spo_ratio', 0) > 0:
                    actions.append(f"增发比例 {record.get('stk_spo_ratio', 0)} @{record.get('stk_spo_price', 0)}")
                split_ratio = record.get('split_ratio', 1)
                if split_ratio != 1:
                    if split_ratio > 1:
                        actions.append(f"拆股 {split_ratio}:1")
                    else:
                        actions.append(f"合股 1:{1/split_ratio:.1f}")
                
                if actions:
                    print(f"     公司行为: {'; '.join(actions)}")
                else:
                    print(f"     公司行为: 无具体行为")
                
                print(f"     前复权因子A: {record.get('forward_adj_factorA', 'N/A')}")
                print(f"     前复权因子B: {record.get('forward_adj_factorB', 'N/A')}")
                print(f"     后复权因子A: {record.get('backward_adj_factorA', 'N/A')}")
                print(f"     后复权因子B: {record.get('backward_adj_factorB', 'N/A')}")
        
        print("=" * 80)

    async def run_tests(self):
        """运行所有测试"""
        print("🧪 开始测试复权因子接口")
        print("=" * 60)
        
        # 健康检查
        if not await self.test_health_check():
            print("❌ 服务不健康，停止测试")
            return
        
        # 测试股票列表
        test_stocks = [
            "HK.00700",    # 腾讯控股
            "HK.00939",    # 建设银行
            "HK.01810",    # 小米集团
            "US.AAPL",     # 苹果
            "US.TSLA",     # 特斯拉
        ]
        
        for stock_code in test_stocks:
            print(f"\n🔍 测试股票: {stock_code}")
            print("-" * 50)
            
            # 测试复权因子
            rehab_data = await self.test_rehab(stock_code)
            self.print_rehab_data(rehab_data, stock_code)
            
            # 间隔避免频率限制
            await asyncio.sleep(1)
        
        print(f"\n✅ 复权因子接口测试完成!")
        print(f"📊 数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    """主函数"""
    tester = RehabTester()
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main()) 