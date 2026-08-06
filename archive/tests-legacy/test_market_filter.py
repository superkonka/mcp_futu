#!/usr/bin/env python3
"""
测试全市场筛选接口
测试条件选股、板块内股票列表、板块列表功能
"""

import asyncio
import json
import aiohttp
from typing import Dict, Any
from datetime import datetime


class MarketFilterTester:
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

    async def test_stock_filter(self, market: str, filter_conditions: list = None) -> Dict[str, Any]:
        """测试条件选股接口"""
        try:
            async with aiohttp.ClientSession() as session:
                # 默认筛选条件：价格在10-100之间，按价格降序排列
                if filter_conditions is None:
                    filter_conditions = [
                        {
                            "stock_field": "CUR_PRICE",
                            "filter_min": 10.0,
                            "filter_max": 100.0,
                            "is_no_filter": False,
                            "sort": "DESCEND"
                        }
                    ]
                
                payload = {
                    "market": market,
                    "filter_list": filter_conditions,
                    "begin": 0,
                    "num": 20,
                    "optimization": {
                        "enable_optimization": True,
                        "only_essential_fields": True,
                        "remove_meaningless_values": True
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/api/market/stock_filter",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    return data
                    
        except Exception as e:
            print(f"❌ 测试条件选股失败: {e}")
            return {"ret_code": -1, "ret_msg": str(e), "data": None}

    async def test_plate_list(self, market: str, plate_set_type: str = "ALL") -> Dict[str, Any]:
        """测试板块列表接口"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "market": market,
                    "plate_set_type": plate_set_type,
                    "optimization": {
                        "enable_optimization": True,
                        "only_essential_fields": True,
                        "remove_meaningless_values": True
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/api/market/plate_list",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    return data
                    
        except Exception as e:
            print(f"❌ 测试板块列表失败: {e}")
            return {"ret_code": -1, "ret_msg": str(e), "data": None}

    async def test_plate_stock(self, plate_code: str) -> Dict[str, Any]:
        """测试板块内股票列表接口"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "plate_code": plate_code,
                    "sort_field": "CUR_PRICE",
                    "sort_dir": "DESCEND",
                    "optimization": {
                        "enable_optimization": True,
                        "only_essential_fields": True,
                        "remove_meaningless_values": True
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/api/market/plate_stock",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    return data
                    
        except Exception as e:
            print(f"❌ 测试板块内股票失败: {e}")
            return {"ret_code": -1, "ret_msg": str(e), "data": None}

    def print_stock_filter_data(self, data: Dict[str, Any], market: str):
        """打印条件选股数据"""
        print(f"\n📊 {market}市场条件选股结果:")
        print("=" * 80)
        
        if data.get("ret_code") != 0:
            print(f"❌ 获取失败: {data.get('ret_msg', '未知错误')}")
            return
        
        result_data = data.get("data", {})
        stock_list = result_data.get("stock_list", [])
        summary = result_data.get("summary", {})
        
        # 打印汇总信息
        print(f"📈 汇总信息:")
        print(f"   筛选出股票数: {summary.get('total_stocks', 0)}")
        print(f"   平均价格: {summary.get('average_price', 0):.2f}")
        print(f"   总市值: {summary.get('total_market_value', 0):,.0f}")
        
        # 市场分布
        market_dist = summary.get('market_distribution', {})
        if market_dist:
            print(f"   市场分布: {', '.join([f'{k}:{v}只' for k, v in market_dist.items()])}")
        
        # 价格分布
        price_dist = summary.get('price_distribution', {})
        if price_dist:
            print(f"   价格分布: {', '.join([f'{k}:{v}只' for k, v in price_dist.items()])}")
        
        # 打印股票列表（前10只）
        if stock_list:
            print(f"\n📝 股票列表 (前{min(10, len(stock_list))}只):")
            for i, stock in enumerate(stock_list[:10], 1):
                code = stock.get('code', 'N/A')
                name = stock.get('name', 'N/A')
                price = stock.get('cur_price', 0)
                change_rate = stock.get('change_rate', 0)
                volume = stock.get('volume', 0)
                market_val = stock.get('market_val', 0)
                
                print(f"   {i:2d}. {code:12s} {name:15s} "
                      f"价格:{price:8.2f} 涨跌:{change_rate:6.2f}% "
                      f"成交量:{volume:>10,} 市值:{market_val:>12,.0f}")
        
        print("=" * 80)

    def print_plate_list_data(self, data: Dict[str, Any], market: str):
        """打印板块列表数据"""
        print(f"\n📊 {market}市场板块列表:")
        print("=" * 80)
        
        if data.get("ret_code") != 0:
            print(f"❌ 获取失败: {data.get('ret_msg', '未知错误')}")
            return
        
        result_data = data.get("data", {})
        plate_list = result_data.get("plate_list", [])
        summary = result_data.get("summary", {})
        
        # 打印汇总信息
        print(f"📈 汇总信息:")
        print(f"   板块总数: {summary.get('total_plates', 0)}")
        
        # 板块类型分布
        type_dist = summary.get('plate_type_distribution', {})
        if type_dist:
            print(f"   类型分布: {', '.join([f'{k}:{v}个' for k, v in type_dist.items()])}")
        
        # 按类型分组显示
        grouped = summary.get('grouped_by_type', {})
        for plate_type, plates in grouped.items():
            print(f"\n📋 {plate_type}板块 ({len(plates)}个):")
            for i, plate in enumerate(plates[:5], 1):  # 只显示前5个
                print(f"   {i}. {plate.get('plate_code', 'N/A'):15s} {plate.get('plate_name', 'N/A')}")
            if len(plates) > 5:
                print(f"   ... 还有{len(plates) - 5}个板块")
        
        print("=" * 80)

    def print_plate_stock_data(self, data: Dict[str, Any], plate_code: str):
        """打印板块内股票数据"""
        print(f"\n📊 板块{plate_code}内股票列表:")
        print("=" * 80)
        
        if data.get("ret_code") != 0:
            print(f"❌ 获取失败: {data.get('ret_msg', '未知错误')}")
            return
        
        result_data = data.get("data", {})
        stock_list = result_data.get("stock_list", [])
        summary = result_data.get("summary", {})
        plate_info = result_data.get("plate_info", {})
        
        # 打印板块信息
        print(f"📈 板块信息:")
        print(f"   板块代码: {plate_info.get('plate_code', 'N/A')}")
        print(f"   所属市场: {plate_info.get('market', 'N/A')}")
        print(f"   股票总数: {summary.get('total_stocks', 0)}")
        
        # 股票类型分布
        type_dist = summary.get('stock_type_distribution', {})
        if type_dist:
            print(f"   类型分布: {', '.join([f'{k}:{v}只' for k, v in type_dist.items()])}")
        
        # 打印股票列表（前15只）
        if stock_list:
            print(f"\n📝 股票列表 (前{min(15, len(stock_list))}只):")
            for i, stock in enumerate(stock_list[:15], 1):
                code = stock.get('code', 'N/A')
                name = stock.get('stock_name', 'N/A')
                stock_type = stock.get('stock_type', 'N/A')
                lot_size = stock.get('lot_size', 0)
                
                print(f"   {i:2d}. {code:12s} {name:20s} "
                      f"类型:{stock_type:8s} 每手:{lot_size:>6}")
        
        print("=" * 80)

    async def run_tests(self):
        """运行所有测试"""
        print("🧪 开始测试全市场筛选接口")
        print("=" * 60)
        
        # 健康检查
        if not await self.test_health_check():
            print("❌ 服务不健康，停止测试")
            return
        
        # 测试1: 获取港股板块列表
        print(f"\n🔍 测试1: 获取港股板块列表")
        print("-" * 50)
        plate_list_data = await self.test_plate_list("HK", "INDUSTRY")
        self.print_plate_list_data(plate_list_data, "港股")
        await asyncio.sleep(1)
        
        # 测试2: 港股条件选股 - 价格在50-200之间
        print(f"\n🔍 测试2: 港股条件选股")
        print("-" * 50)
        filter_conditions = [
            {
                "stock_field": "CUR_PRICE",
                "filter_min": 50.0,
                "filter_max": 200.0,
                "is_no_filter": False,
                "sort": "DESCEND"
            },
            {
                "stock_field": "VOLUME",
                "filter_min": 100000,
                "is_no_filter": False,
                "sort": "NONE"
            }
        ]
        stock_filter_data = await self.test_stock_filter("HK", filter_conditions)
        self.print_stock_filter_data(stock_filter_data, "港股")
        await asyncio.sleep(1)
        
        # 测试3: 获取美股板块列表
        print(f"\n🔍 测试3: 获取美股板块列表")
        print("-" * 50)
        us_plate_data = await self.test_plate_list("US", "INDUSTRY")
        self.print_plate_list_data(us_plate_data, "美股")
        await asyncio.sleep(1)
        
        # 测试4: 美股条件选股 - 价格在20-100之间
        print(f"\n🔍 测试4: 美股条件选股")
        print("-" * 50)
        us_filter_conditions = [
            {
                "stock_field": "CUR_PRICE",
                "filter_min": 20.0,
                "filter_max": 100.0,
                "is_no_filter": False,
                "sort": "DESCEND"
            }
        ]
        us_stock_data = await self.test_stock_filter("US", us_filter_conditions)
        self.print_stock_filter_data(us_stock_data, "美股")
        await asyncio.sleep(1)
        
        # 测试5: 获取板块内股票 (使用一个知名板块)
        print(f"\n🔍 测试5: 获取板块内股票")
        print("-" * 50)
        
        # 如果之前获取到了板块列表，使用第一个板块
        if (plate_list_data.get("ret_code") == 0 and 
            plate_list_data.get("data", {}).get("plate_list")):
            first_plate = plate_list_data["data"]["plate_list"][0]
            plate_code = first_plate.get("plate_code", "HK.BK1001")
        else:
            plate_code = "HK.BK1001"  # 默认使用一个港股板块
        
        plate_stock_data = await self.test_plate_stock(plate_code)
        self.print_plate_stock_data(plate_stock_data, plate_code)
        
        print(f"\n✅ 全市场筛选接口测试完成!")
        print(f"📊 数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 富途API限制提醒
        print(f"\n⚠️  API限制提醒:")
        print(f"   - 条件选股: 每30秒最多10次请求")
        print(f"   - 每页最多返回200个结果")
        print(f"   - 建议筛选条件不超过250个")


async def main():
    """主函数"""
    tester = MarketFilterTester()
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main()) 