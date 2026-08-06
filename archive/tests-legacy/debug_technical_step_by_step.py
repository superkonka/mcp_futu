#!/usr/bin/env python3
"""
逐步调试技术指标计算，隔离问题
"""

import sys
import os
import asyncio
import traceback
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_step_by_step():
    """逐步测试每个组件"""
    
    print("🔍 步骤1: 测试模型创建...")
    
    try:
        from models.analysis_models import TechnicalAnalysisRequest, EnhancedAPIResponse
        
        # 创建最简单的请求
        request = TechnicalAnalysisRequest(
            code="HK.01810",
            period=14,
            indicators=["macd"]  # 只要一个指标
        )
        
        print("✅ 模型创建成功")
        print(f"请求: {request.code}, 指标: {request.indicators}")
        
    except Exception as e:
        print(f"❌ 模型创建失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤2: 测试请求模型序列化...")
    
    try:
        request_dict = request.dict()
        print("✅ 请求序列化成功")
        print(f"序列化数据: {request_dict}")
        
    except Exception as e:
        print(f"❌ 序列化失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤3: 测试模拟K线数据...")
    
    try:
        # 创建模拟K线数据
        kline_data = []
        base_price = 54.0
        
        for i in range(30):
            price = base_price + (i % 10 - 5) * 0.5
            kline_data.append({
                "time": (datetime.now() - timedelta(days=29-i)).strftime('%Y-%m-%d'),
                "open": price - 0.1,
                "high": price + 0.3,
                "low": price - 0.2,
                "close": price,
                "volume": 1000000 + (i % 5) * 100000,
                "turnover": price * 1000000
            })
        
        print(f"✅ 模拟数据创建成功，共 {len(kline_data)} 条")
        
    except Exception as e:
        print(f"❌ 模拟数据创建失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤4: 测试技术指标导入...")
    
    try:
        from analysis.technical_indicators import TechnicalIndicators, IndicatorConfig
        print("✅ 技术指标模块导入成功")
        
    except Exception as e:
        print(f"❌ 技术指标导入失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤5: 测试指标配置创建...")
    
    try:
        config = IndicatorConfig(
            macd_fast=request.macd_fast,
            macd_slow=request.macd_slow,
            macd_signal=request.macd_signal,
            rsi_period=request.rsi_period,
            bollinger_period=request.bollinger_period,
        )
        print("✅ 指标配置创建成功")
        
    except Exception as e:
        print(f"❌ 指标配置创建失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤6: 测试技术指标对象创建...")
    
    try:
        technical_data = TechnicalIndicators.from_kline_data(kline_data, config)
        print("✅ 技术指标对象创建成功")
        
    except Exception as e:
        print(f"❌ 技术指标对象创建失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤7: 测试指标计算...")
    
    try:
        indicators = technical_data.calculate_all_indicators()
        print("✅ 指标计算成功")
        print(f"计算结果包含: {list(indicators.keys())}")
        
    except Exception as e:
        print(f"❌ 指标计算失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤8: 测试数据清理...")
    
    try:
        # 导入数据清理函数
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from main_enhanced import _clean_indicator_data
        
        print("原始指标数据示例:")
        print(f"  MACD current: {indicators['trend_indicators']['macd']['current']}")
        print(f"  MA current: {indicators['trend_indicators']['moving_averages']['current']}")
        
        clean_indicators = _clean_indicator_data(indicators)
        print("✅ 数据清理成功")
        
        print("清理后指标数据示例:")
        if 'trend_indicators' in clean_indicators and 'macd' in clean_indicators['trend_indicators']:
            print(f"  MACD current: {clean_indicators['trend_indicators']['macd'].get('current')}")
        if 'trend_indicators' in clean_indicators and 'moving_averages' in clean_indicators['trend_indicators']:
            print(f"  MA current: {clean_indicators['trend_indicators']['moving_averages'].get('current')}")
        
    except Exception as e:
        print(f"❌ 数据清理失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤9: 测试响应模型创建...")
    
    try:
        from models.analysis_models import TechnicalAnalysisResponse
        
        response_data = TechnicalAnalysisResponse(
            code=request.code,
            period=request.period,
            data_points=len(kline_data),
            trend_indicators=clean_indicators.get("trend_indicators"),
            momentum_indicators=clean_indicators.get("momentum_indicators"),
            volatility_indicators=clean_indicators.get("volatility_indicators"),
            volume_indicators=clean_indicators.get("volume_indicators"),
            summary=clean_indicators.get("summary"),
            timestamp=datetime.now().isoformat()
        )
        print("✅ 响应模型创建成功")
        
    except Exception as e:
        print(f"❌ 响应模型创建失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤10: 测试API响应包装...")
    
    try:
        api_response = EnhancedAPIResponse(
            ret_code=0,
            ret_msg="技术分析计算完成",
            data=response_data,
            execution_time=0.1,
            cache_hit=False,
            data_source="calculated",
            timestamp=datetime.now().isoformat()
        )
        print("✅ API响应包装成功")
        
    except Exception as e:
        print(f"❌ API响应包装失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🔍 步骤11: 测试最终序列化...")
    
    try:
        final_dict = api_response.model_dump()  # 使用新的Pydantic V2方法
        print("✅ 最终序列化成功")
        print(f"响应大小: {len(str(final_dict))} 字符")
        
    except Exception as e:
        print(f"❌ 最终序列化失败: {e}")
        traceback.print_exc()
        return False
    
    print("\n🎉 所有步骤都成功完成！")
    return True

if __name__ == "__main__":
    print("🧪 开始逐步测试技术指标组件...")
    print("="*50)
    
    success = asyncio.run(test_step_by_step())
    
    print("="*50)
    if success:
        print("✅ 所有组件测试通过，问题可能在API集成层面")
    else:
        print("❌ 发现组件问题") 