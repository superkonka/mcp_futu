#!/usr/bin/env python3
"""
富途MCP增强版功能演示
展示缓存系统、技术分析等新功能的使用
"""

import asyncio
import httpx
import json
import time
from datetime import datetime

# 服务地址
BASE_URL = "http://localhost:8001"

class EnhancedFutuDemo:
    """增强版功能演示"""
    
    def __init__(self):
        self.client = httpx.AsyncClient()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def check_health(self):
        """检查服务健康状态"""
        print("\n🔍 检查服务健康状态...")
        
        try:
            response = await self.client.get(f"{BASE_URL}/health")
            data = response.json()
            
            print(f"服务状态: {data['status']}")
            print(f"富途连接: {data['futu_connected']}")
            print(f"缓存可用: {data['cache_available']}")
            print(f"检查时间: {data['timestamp']}")
            
            if data.get('cache_stats'):
                cache_stats = data['cache_stats']
                print(f"内存缓存: {cache_stats.get('memory_cache_size', 0)} 条目")
                print(f"Redis可用: {cache_stats.get('redis_available', False)}")
                print(f"SQLite可用: {cache_stats.get('sqlite_available', False)}")
            
            return data['status'] == 'healthy'
            
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
            return False
    
    async def test_cache_status(self):
        """测试缓存状态查询"""
        print("\n📊 查询缓存状态...")
        
        try:
            response = await self.client.get(f"{BASE_URL}/api/cache/status?detailed=true")
            data = response.json()
            
            if data['ret_code'] == 0:
                stats = data['data']['stats']
                print(f"✅ 缓存状态查询成功:")
                print(f"   内存缓存: {stats['memory_cache_size']}/{stats['memory_max_size']} ({stats['memory_usage_ratio']*100:.1f}%)")
                print(f"   Redis状态: {'✅' if stats['redis_available'] else '❌'}")
                print(f"   SQLite状态: {'✅' if stats['sqlite_available'] else '❌'}")
                print(f"   健康状态: {data['data']['health_status']}")
                
                if data['data']['recommendations']:
                    print(f"   建议: {', '.join(data['data']['recommendations'])}")
            else:
                print(f"❌ 查询失败: {data['ret_msg']}")
                
        except Exception as e:
            print(f"❌ 缓存状态查询异常: {e}")
    
    async def test_kline_with_cache(self):
        """测试带缓存的K线获取"""
        print("\n📈 测试缓存K线获取...")
        
        request_data = {
            "code": "HK.00700",  # 腾讯控股
            "start": "2025-06-01",
            "end": "2025-06-13",
            "ktype": "K_DAY",
            "max_count": 100,
            "optimization": {
                "remove_duplicates": True,
                "essential_fields_only": True,
                "remove_meaningless_values": True
            }
        }
        
        try:
            # 第一次请求（从API）
            print("🔍 第一次请求（从API）...")
            start_time = time.time()
            
            response = await self.client.post(
                f"{BASE_URL}/api/quote/history_kline",
                json=request_data
            )
            
            first_time = time.time() - start_time
            data = response.json()
            
            if data['ret_code'] == 0:
                kline_data = data['data']['kline_data']
                print(f"✅ 获取成功: {len(kline_data)} 条K线数据")
                print(f"   执行时间: {first_time:.3f}s")
                print(f"   缓存命中: {data['data'].get('cache_hit', False)}")
                print(f"   数据源: {data['data'].get('data_source', 'unknown')}")
                
                # 显示最新几条数据
                if kline_data:
                    print("   最新数据:")
                    for i, kline in enumerate(kline_data[-3:]):
                        print(f"     {kline.get('time_key', '')}: 收盘价 {kline.get('close', 'N/A')}")
            else:
                print(f"❌ 获取失败: {data['ret_msg']}")
                return
            
            # 第二次请求（从缓存）
            print("\n🔍 第二次请求（从缓存）...")
            start_time = time.time()
            
            response = await self.client.post(
                f"{BASE_URL}/api/quote/history_kline",
                json=request_data
            )
            
            second_time = time.time() - start_time
            data = response.json()
            
            if data['ret_code'] == 0:
                print(f"✅ 获取成功: {len(data['data']['kline_data'])} 条K线数据")
                print(f"   执行时间: {second_time:.3f}s")
                print(f"   缓存命中: {data['data'].get('cache_hit', False)}")
                print(f"   性能提升: {((first_time - second_time) / first_time * 100):.1f}%")
            else:
                print(f"❌ 获取失败: {data['ret_msg']}")
                
        except Exception as e:
            print(f"❌ K线获取测试异常: {e}")
    
    async def test_technical_analysis(self):
        """测试技术分析功能"""
        print("\n🧮 测试技术分析...")
        
        request_data = {
            "code": "HK.00700",
            "period": 60,  # 60天分析周期
            "ktype": "K_DAY",
            "indicators": ["all"],
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "rsi_period": 14,
            "bollinger_period": 20,
            "ma_periods": [5, 10, 20, 30, 60]
        }
        
        try:
            start_time = time.time()
            
            response = await self.client.post(
                f"{BASE_URL}/api/analysis/technical_indicators",
                json=request_data
            )
            
            execution_time = time.time() - start_time
            data = response.json()
            
            if data['ret_code'] == 0:
                analysis = data['data']
                print(f"✅ 技术分析完成:")
                print(f"   股票代码: {analysis['code']}")
                print(f"   分析周期: {analysis['period']} 天")
                print(f"   数据点数: {analysis['data_points']} 个")
                print(f"   执行时间: {execution_time:.3f}s")
                print(f"   缓存命中: {data.get('cache_hit', False)}")
                
                # 显示趋势指标
                if analysis.get('trend_indicators'):
                    trend = analysis['trend_indicators']
                    print("\n📈 趋势指标:")
                    
                    if 'macd' in trend:
                        macd = trend['macd']
                        current = macd.get('current', {})
                        print(f"   MACD: {current.get('macd', 'N/A'):.4f}")
                        print(f"   信号线: {current.get('signal', 'N/A'):.4f}")
                        print(f"   柱状图: {current.get('histogram', 'N/A'):.4f}")
                        print(f"   信号: {macd.get('signal', 'N/A')}")
                    
                    if 'moving_averages' in trend:
                        ma = trend['moving_averages']
                        current = ma.get('current', {})
                        print(f"   MA5: {current.get('ma_5', 'N/A'):.2f}")
                        print(f"   MA20: {current.get('ma_20', 'N/A'):.2f}")
                        print(f"   MA信号: {ma.get('signal', 'N/A')}")
                
                # 显示动量指标
                if analysis.get('momentum_indicators'):
                    momentum = analysis['momentum_indicators']
                    print("\n⚡ 动量指标:")
                    
                    if 'rsi' in momentum:
                        rsi = momentum['rsi']
                        print(f"   RSI: {rsi.get('current', 'N/A'):.2f}")
                        print(f"   RSI信号: {rsi.get('signal', 'N/A')}")
                    
                    if 'kdj' in momentum:
                        kdj = momentum['kdj']
                        current = kdj.get('current', {})
                        print(f"   KDJ K: {current.get('k', 'N/A'):.2f}")
                        print(f"   KDJ D: {current.get('d', 'N/A'):.2f}")
                        print(f"   KDJ信号: {kdj.get('signal', 'N/A')}")
                
                # 显示波动性指标
                if analysis.get('volatility_indicators'):
                    volatility = analysis['volatility_indicators']
                    print("\n🌊 波动性指标:")
                    
                    if 'bollinger_bands' in volatility:
                        bb = volatility['bollinger_bands']
                        current = bb.get('current', {})
                        print(f"   布林上轨: {current.get('upper', 'N/A'):.2f}")
                        print(f"   布林中轨: {current.get('middle', 'N/A'):.2f}")
                        print(f"   布林下轨: {current.get('lower', 'N/A'):.2f}")
                        print(f"   布林信号: {bb.get('signal', 'N/A')}")
                
                # 显示总结
                if analysis.get('summary'):
                    summary = analysis['summary']
                    print("\n📋 分析总结:")
                    for key, value in summary.items():
                        print(f"   {key}: {value}")
                        
            else:
                print(f"❌ 技术分析失败: {data['ret_msg']}")
                
        except Exception as e:
            print(f"❌ 技术分析异常: {e}")
    
    async def test_single_indicators(self):
        """测试单独指标获取"""
        print("\n🎯 测试单独指标获取...")
        
        base_request = {
            "code": "HK.00700",
            "period": 30,
            "ktype": "K_DAY"
        }
        
        # 测试MACD
        try:
            print("📊 获取MACD指标...")
            response = await self.client.post(
                f"{BASE_URL}/api/analysis/macd",
                json=base_request
            )
            
            data = response.json()
            if data['ret_code'] == 0:
                trend = data['data'].get('trend_indicators', {})
                if 'macd' in trend:
                    macd = trend['macd']
                    print(f"✅ MACD获取成功: {macd.get('signal', 'N/A')}")
                else:
                    print("⚠️ MACD数据不完整")
            else:
                print(f"❌ MACD获取失败: {data['ret_msg']}")
                
        except Exception as e:
            print(f"❌ MACD测试异常: {e}")
        
        # 测试RSI
        try:
            print("📊 获取RSI指标...")
            response = await self.client.post(
                f"{BASE_URL}/api/analysis/rsi",
                json=base_request
            )
            
            data = response.json()
            if data['ret_code'] == 0:
                momentum = data['data'].get('momentum_indicators', {})
                if 'rsi' in momentum:
                    rsi = momentum['rsi']
                    print(f"✅ RSI获取成功: {rsi.get('current', 'N/A'):.2f} ({rsi.get('signal', 'N/A')})")
                else:
                    print("⚠️ RSI数据不完整")
            else:
                print(f"❌ RSI获取失败: {data['ret_msg']}")
                
        except Exception as e:
            print(f"❌ RSI测试异常: {e}")
    
    async def test_cache_operations(self):
        """测试缓存操作"""
        print("\n🗄️ 测试缓存操作...")
        
        # 预加载数据
        try:
            print("📥 预加载缓存数据...")
            preload_request = {
                "symbols": ["HK.00700", "HK.00005", "HK.00001"],
                "days": 30,
                "ktypes": ["K_DAY"]
            }
            
            response = await self.client.post(
                f"{BASE_URL}/api/cache/preload",
                json=preload_request
            )
            
            data = response.json()
            if data['ret_code'] == 0:
                operation = data['data']
                print(f"✅ 预加载成功: {operation['message']}")
                print(f"   执行时间: {operation.get('execution_time', 0):.3f}s")
            else:
                print(f"❌ 预加载失败: {data['ret_msg']}")
                
        except Exception as e:
            print(f"❌ 预加载异常: {e}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 启动富途MCP增强版功能演示")
        print("=" * 50)
        
        # 检查服务健康状态
        if not await self.check_health():
            print("❌ 服务不健康，请检查服务是否正常启动")
            return
        
        # 运行各项测试
        await self.test_cache_status()
        await self.test_kline_with_cache()
        await self.test_technical_analysis()
        await self.test_single_indicators()
        await self.test_cache_operations()
        
        print("\n" + "=" * 50)
        print("🎉 增强版功能演示完成!")
        print("\n💡 使用提示:")
        print("1. 缓存系统自动优化数据获取速度")
        print("2. 技术分析提供专业的股票指标计算")
        print("3. 所有接口都支持缓存，提高性能")
        print("4. 可以通过 /api/cache/status 监控缓存状态")


async def main():
    """主函数"""
    async with EnhancedFutuDemo() as demo:
        await demo.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main()) 