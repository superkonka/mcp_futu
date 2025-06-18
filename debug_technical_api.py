#!/usr/bin/env python3
"""
逐步调试技术指标API
"""

import sys
import os
import asyncio
import traceback
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def debug_technical_indicators():
    """逐步调试技术指标计算流程"""
    
    try:
        print("🔍 步骤1: 导入必需模块...")
        
        from models.analysis_models import (
            TechnicalAnalysisRequest, 
            TechnicalAnalysisResponse, 
            EnhancedAPIResponse,
            IndicatorConfig
        )
        from models.futu_models import HistoryKLineRequest
        from analysis.technical_indicators import TechnicalIndicators
        from cache.cache_manager import DataCacheManager
        
        print("✅ 所有模块导入成功")
        
        print("\n🔍 步骤2: 创建请求对象...")
        request = TechnicalAnalysisRequest(
            code="HK.01810",
            indicators=["macd", "rsi", "bollinger_bands"],
            period=14,
            ktype="K_DAY",
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            rsi_period=14,
            bollinger_period=20,
            optimization={
                "enable_optimization": True,
                "only_essential_fields": True
            }
        )
        print("✅ 请求对象创建成功")
        
        print("\n🔍 步骤3: 初始化缓存管理器...")
        cache_manager = DataCacheManager()
        print("✅ 缓存管理器初始化成功")
        
        print("\n🔍 步骤4: 准备K线请求...")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=request.period)).strftime('%Y-%m-%d')
        
        kline_request = HistoryKLineRequest(
            code=request.code,
            start=start_date,
            end=end_date,
            ktype=request.ktype,
            max_count=request.period * 2,
            optimization=request.optimization
        )
        print("✅ K线请求准备完成")
        
        print("\n🔍 步骤5: 模拟K线数据...")
        # 创建一些模拟数据来测试计算
        kline_data = []
        base_price = 54.0
        
        for i in range(30):  # 30天数据
            price = base_price + (i % 10 - 5) * 0.5  # 模拟价格波动
            volume = 1000000 + (i % 5) * 100000
            
            kline_data.append({
                "time": (datetime.now() - timedelta(days=29-i)).strftime('%Y-%m-%d'),
                "open": price - 0.1,
                "high": price + 0.3,
                "low": price - 0.2,
                "close": price,
                "volume": volume,
                "turnover": price * volume
            })
        
        print(f"✅ 模拟了 {len(kline_data)} 条K线数据")
        
        print("\n🔍 步骤6: 创建指标配置...")
        config = IndicatorConfig(
            macd_fast=request.macd_fast,
            macd_slow=request.macd_slow,
            macd_signal=request.macd_signal,
            rsi_period=request.rsi_period,
            rsi_overbought=request.rsi_overbought,
            rsi_oversold=request.rsi_oversold,
            bollinger_period=request.bollinger_period,
            bollinger_std=request.bollinger_std,
            ma_periods=request.ma_periods
        )
        print("✅ 指标配置创建成功")
        
        print("\n🔍 步骤7: 计算技术指标...")
        technical_data = TechnicalIndicators.from_kline_data(kline_data, config)
        indicators = technical_data.calculate_all_indicators()
        print("✅ 技术指标计算成功")
        print(f"指标数据键: {list(indicators.keys())}")
        
        print("\n🔍 步骤8: 构建响应数据...")
        response_data = TechnicalAnalysisResponse(
            code=request.code,
            period=request.period,
            data_points=len(kline_data),
            trend_indicators=indicators.get("trend_indicators"),
            momentum_indicators=indicators.get("momentum_indicators"),
            volatility_indicators=indicators.get("volatility_indicators"),
            volume_indicators=indicators.get("volume_indicators"),
            summary=indicators.get("summary"),
            timestamp=datetime.now().isoformat()
        )
        print("✅ 响应数据构建成功")
        
        print("\n🔍 步骤9: 创建API响应...")
        api_response = EnhancedAPIResponse(
            ret_code=0,
            ret_msg="技术分析计算完成",
            data=response_data,
            execution_time=0.1,
            cache_hit=False,
            data_source="calculated",
            timestamp=datetime.now().isoformat()
        )
        print("✅ API响应创建成功")
        
        print("\n🔍 步骤10: 序列化测试...")
        response_dict = api_response.dict()
        print("✅ 响应序列化成功")
        print(f"响应数据结构: {type(response_dict)} 包含 {len(response_dict)} 个字段")
        
        print("\n🎉 所有步骤完成，技术指标计算流程正常！")
        return True
        
    except Exception as e:
        print(f"\n❌ 步骤失败: {e}")
        traceback.print_exc()
        return False

async def test_direct_api_call():
    """测试直接API调用"""
    print("\n" + "="*50)
    print("🧪 测试直接API调用...")
    
    try:
        # 导入主应用
        from main_enhanced import get_technical_indicators
        from models.analysis_models import TechnicalAnalysisRequest
        
        # 创建请求
        request = TechnicalAnalysisRequest(
            code="HK.01810",
            indicators=["macd", "rsi"],  # 简化指标列表
            period=14
        )
        
        print("📞 直接调用API函数...")
        result = await get_technical_indicators(request)
        
        print(f"✅ API调用成功")
        print(f"返回码: {result.ret_code}")
        print(f"消息: {result.ret_msg}")
        
        if result.ret_code == 0:
            print(f"数据类型: {type(result.data)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 直接API调用失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔬 开始逐步调试技术指标API...")
    print("="*50)
    
    # 运行异步调试
    success1 = asyncio.run(debug_technical_indicators())
    success2 = asyncio.run(test_direct_api_call())
    
    print("\n" + "="*50)
    if success1 and success2:
        print("🎯 调试完成：所有步骤成功")
    else:
        print("🚨 调试发现问题") 