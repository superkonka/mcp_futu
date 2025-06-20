#!/usr/bin/env python3
"""
富途MCP增强服务 - 完整功能测试脚本
测试所有API端点的功能和性能
"""

import asyncio
import time
import httpx
import json
from typing import List, Dict

BASE_URL = "http://localhost:8001"

class FutuServiceTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = []
    
    async def test_endpoint(self, name: str, method: str, endpoint: str, data: dict = None):
        """测试单个API端点"""
        print(f"🧪 测试 {name}...")
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = await self.client.get(f"{self.base_url}{endpoint}")
            elif method.upper() == "POST":
                response = await self.client.post(
                    f"{self.base_url}{endpoint}",
                    json=data,
                    headers={"Content-Type": "application/json"}
                )
            elif method.upper() == "DELETE":
                if data:
                    response = await self.client.delete(
                        f"{self.base_url}{endpoint}",
                        params=data  # 使用params而不是json
                    )
                else:
                    response = await self.client.delete(f"{self.base_url}{endpoint}")
            
            execution_time = time.time() - start_time
            
            if response.status_code == 200:
                result_data = response.json()
                if isinstance(result_data, dict) and "ret_code" in result_data:
                    success = result_data["ret_code"] == 0
                    message = result_data.get("ret_msg", "成功")
                else:
                    success = True
                    message = "成功"
                
                self.test_results.append({
                    "name": name,
                    "success": success,
                    "time": execution_time,
                    "message": message,
                    "status_code": response.status_code
                })
                
                status = "✅" if success else "⚠️"
                print(f"   {status} {name}: {execution_time:.3f}s - {message}")
                return True, result_data
            else:
                print(f"   ❌ {name}: HTTP {response.status_code}")
                self.test_results.append({
                    "name": name,
                    "success": False,
                    "time": execution_time,
                    "message": f"HTTP {response.status_code}",
                    "status_code": response.status_code
                })
                return False, None
                
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"   ❌ {name}: {str(e)}")
            self.test_results.append({
                "name": name,
                "success": False,
                "time": execution_time,
                "message": str(e),
                "status_code": 0
            })
            return False, None
    
    async def run_all_tests(self):
        """运行所有功能测试"""
        print("🚀 开始完整功能测试...\n")
        
        # 1. 健康检查
        print("📊 基础服务测试")
        await self.test_endpoint("健康检查", "GET", "/health")
        await self.test_endpoint("缓存状态", "GET", "/api/cache/status")
        await self.test_endpoint("时间查询", "GET", "/api/time/current")
        print()
        
        # 2. 股票报价测试
        print("💹 股票报价测试")
        await self.test_endpoint(
            "单股票报价", "POST", "/api/quote/stock_quote",
            {"code_list": ["HK.00700"]}
        )
        await self.test_endpoint(
            "批量股票报价", "POST", "/api/quote/stock_quote",
            {"code_list": ["HK.00700", "HK.09660", "HK.00005"]}
        )
        print()
        
        # 3. K线数据测试
        print("📈 K线数据测试")
        await self.test_endpoint(
            "日线K线", "POST", "/api/quote/history_kline",
            {"code": "HK.00700", "ktype": "K_DAY", "max_count": 30}
        )
        await self.test_endpoint(
            "30分钟K线", "POST", "/api/quote/history_kline",
            {"code": "HK.00700", "ktype": "K_30M", "max_count": 48}
        )
        print()
        
        # 4. 技术指标测试
        print("🧮 技术指标测试")
        await self.test_endpoint(
            "RSI指标", "POST", "/api/analysis/technical_indicators",
            {"code": "HK.00700", "indicators": ["rsi"], "ktype": "K_DAY"}
        )
        await self.test_endpoint(
            "MACD指标", "POST", "/api/analysis/technical_indicators",
            {"code": "HK.00700", "indicators": ["macd"], "ktype": "K_DAY"}
        )
        await self.test_endpoint(
            "全指标分析", "POST", "/api/analysis/technical_indicators",
            {"code": "HK.00700", "indicators": ["all"], "ktype": "K_DAY"}
        )
        print()
        
        # 5. 缓存管理测试
        print("🗄️ 缓存管理测试")
        await self.test_endpoint(
            "预加载缓存", "POST", "/api/cache/preload",
            {"symbols": ["HK.00700"], "days": 7, "ktypes": ["K_DAY"]}
        )
        await self.test_endpoint(
            "清理内存缓存", "DELETE", "/api/cache/clear",
            {"cache_type": "memory"}
        )
        print()
        
        # 6. 性能测试
        print("⚡ 性能测试（缓存命中）")
        # 先请求一次建立缓存
        await self.test_endpoint(
            "建立缓存", "POST", "/api/quote/stock_quote",
            {"code_list": ["HK.00700"]}
        )
        # 再请求测试缓存命中性能
        await self.test_endpoint(
            "缓存命中测试", "POST", "/api/quote/stock_quote",
            {"code_list": ["HK.00700"]}
        )
        print()
        
        # 生成测试报告
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        print("📋 测试报告")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - successful_tests
        
        print(f"总测试数: {total_tests}")
        print(f"成功: {successful_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"成功率: {(successful_tests/total_tests*100):.1f}%")
        print()
        
        # 性能统计
        successful_times = [r["time"] for r in self.test_results if r["success"]]
        if successful_times:
            avg_time = sum(successful_times) / len(successful_times)
            max_time = max(successful_times)
            min_time = min(successful_times)
            
            print("📊 性能统计")
            print(f"平均响应时间: {avg_time:.3f}s")
            print(f"最快响应: {min_time:.3f}s")
            print(f"最慢响应: {max_time:.3f}s")
            print()
        
        # 失败测试详情
        if failed_tests > 0:
            print("❌ 失败测试详情")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  • {result['name']}: {result['message']}")
            print()
        
        # 系统状态建议
        if successful_tests / total_tests >= 0.9:
            print("🎉 系统运行良好！所有核心功能正常。")
        elif successful_tests / total_tests >= 0.7:
            print("⚠️  系统基本正常，但有部分功能异常，建议检查。")
        else:
            print("🚨 系统存在较多问题，建议重启服务或检查配置。")
        
        print("=" * 60)
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

async def main():
    """主函数"""
    print("🔬 富途MCP增强服务 - 完整功能测试")
    print(f"🎯 测试目标: {BASE_URL}")
    print("=" * 60)
    print()
    
    tester = FutuServiceTester()
    
    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main()) 