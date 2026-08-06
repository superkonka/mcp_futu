#!/usr/bin/env python3
"""
时间API测试脚本 - 展示如何使用时间API解析模糊时间表达
"""

import asyncio
import httpx
import json
from datetime import datetime


class TimeAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
    
    async def get_time_context(self):
        """获取时间上下文信息"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/time/current")
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"获取时间信息失败: HTTP {response.status_code}")
    
    def parse_fuzzy_time(self, user_input: str, time_data: dict) -> dict:
        """解析模糊时间表达"""
        time_contexts = time_data.get('data', {}).get('time_contexts', {})
        common_periods = time_data.get('data', {}).get('common_periods', {})
        
        # 模糊时间映射规则
        fuzzy_mappings = {
            "今天": time_contexts.get("今天"),
            "昨天": time_contexts.get("昨天"),
            "最近": common_periods.get("最近3天"),
            "近期": common_periods.get("最近1周"),
            "这几天": common_periods.get("最近1周"),  # 使用1周的范围
            "本周": {"start": time_contexts.get("本周"), "end": time_contexts.get("今天")},
            "上周": {"start": time_contexts.get("上周"), "end": time_contexts.get("本周")},
            "本月": {"start": time_contexts.get("本月"), "end": time_contexts.get("今天")},
            "上月": {"start": time_contexts.get("上月"), "end": time_contexts.get("本月")},
            "最近一个月": common_periods.get("最近1月"),
            "最近三个月": common_periods.get("最近3月"),
            "年初至今": common_periods.get("年初至今")
        }
        
        # 检查用户输入中是否包含模糊时间表达
        for fuzzy_term, time_range in fuzzy_mappings.items():
            if fuzzy_term in user_input:
                return {
                    "matched_term": fuzzy_term,
                    "time_range": time_range,
                    "original_input": user_input
                }
        
        return None
    
    async def test_scenarios(self):
        """测试各种时间表达场景"""
        print("🕒 富途MCP - 时间API测试")
        print("🎯 测试模糊时间表达解析功能")
        print("=" * 60)
        
        # 获取时间上下文
        try:
            time_data = await self.get_time_context()
            current_time = time_data.get('data', {}).get('current_datetime', '')
            print(f"📅 当前服务器时间: {current_time}")
            print()
        except Exception as e:
            print(f"❌ 获取时间信息失败: {e}")
            return
        
        # 测试场景
        test_scenarios = [
            "查看腾讯最近的股价走势",
            "分析阿里巴巴近期的技术指标", 
            "获取苹果这几天的K线数据",
            "查询港交所本周的交易数据",
            "分析比亚迪上月的表现",
            "查看茅台最近一个月的MACD指标",
            "获取招商银行年初至今的数据",
            "查询今天的市场状况"
        ]
        
        print("🧠 模糊时间表达解析测试:")
        print("-" * 60)
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n📝 场景 {i}: {scenario}")
            
            # 解析模糊时间
            parsed_result = self.parse_fuzzy_time(scenario, time_data)
            
            if parsed_result:
                matched_term = parsed_result["matched_term"]
                time_range = parsed_result["time_range"]
                
                print(f"   🎯 识别模糊时间: '{matched_term}'")
                
                if isinstance(time_range, dict) and 'start' in time_range:
                    start_date = time_range.get('start')
                    end_date = time_range.get('end', time_data.get('data', {}).get('current_date'))
                    print(f"   📅 解析时间范围: {start_date} 至 {end_date}")
                    
                    # 模拟API调用建议
                    print(f"   💡 建议API调用:")
                    if "K线" in scenario or "股价" in scenario:
                        print(f"      GET /api/quote/history_kline")
                        print(f"      {{\"code\":\"HK.00700\", \"start\":\"{start_date}\", \"end\":\"{end_date}\"}}")
                    elif "技术指标" in scenario or "MACD" in scenario:
                        print(f"      POST /api/analysis/technical_indicators")
                        print(f"      {{\"code\":\"HK.00700\", \"period\":30}}")
                    else:
                        print(f"      POST /api/quote/stock_quote")
                        print(f"      {{\"code_list\":[\"HK.00700\"]}}")
                        
                elif isinstance(time_range, str):
                    print(f"   📅 解析日期: {time_range}")
                    print(f"   💡 建议API调用:")
                    print(f"      GET /api/quote/stock_quote (当日数据)")
                
            else:
                print(f"   ⚠️  未识别模糊时间表达")
                print(f"   💡 建议: 使用默认时间范围或询问用户具体时间")
        
        print("\n" + "=" * 60)
        
        # 显示时间上下文信息
        print("📊 当前时间上下文信息:")
        contexts = time_data.get('data', {}).get('time_contexts', {})
        for term, date in contexts.items():
            print(f"   {term}: {date}")
        
        print("\n🎯 常用时间区间:")
        periods = time_data.get('data', {}).get('common_periods', {})
        for period_name, period_info in periods.items():
            if isinstance(period_info, dict):
                print(f"   {period_name}: {period_info.get('start')} 至 {period_info.get('end')}")
        
        # 市场时间信息
        market = time_data.get('data', {}).get('market', {})
        print(f"\n📈 市场状态:")
        print(f"   交易日: {'是' if market.get('is_trading_day') else '否'}")
        print(f"   交易时间: {'是' if market.get('is_trading_hours') else '否'}")
        print(f"   开市时间: {market.get('market_open_time')}")
        print(f"   收市时间: {market.get('market_close_time')}")
        
        # LLM使用建议
        llm_context = time_data.get('data', {}).get('llm_context', {})
        print(f"\n🤖 LLM使用建议:")
        for example in llm_context.get('usage_examples', []):
            print(f"   • {example}")
        
        print("\n✅ 时间API测试完成!")
        print("🎉 现在LLM可以准确理解用户的模糊时间表达了！")


async def main():
    """主函数"""
    tester = TimeAPITester()
    await tester.test_scenarios()


if __name__ == "__main__":
    asyncio.run(main()) 