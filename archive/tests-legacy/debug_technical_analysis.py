#!/usr/bin/env python3
"""
技术分析调试脚本
"""

import numpy as np
import pandas as pd
import sys
import os
import traceback
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_simple_test_data():
    """创建简单的测试数据"""
    dates = [datetime.now() - timedelta(days=50-i-1) for i in range(50)]
    
    data = []
    for i, date in enumerate(dates):
        price = 100 + i * 0.5  # 简单的线性上涨
        data.append({
            'time_key': date.strftime('%Y-%m-%d'),
            'open': price,
            'high': price * 1.02,
            'low': price * 0.98,
            'close': price,
            'volume': 1000000
        })
    
    return data

def test_basic_functionality():
    """测试基本功能"""
    print("🧪 测试基本功能...")
    
    try:
        from analysis.technical_indicators import TechnicalIndicators, TechnicalData
        print("✅ 导入成功")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        traceback.print_exc()
        return False
    
    try:
        # 创建测试数据
        test_data = create_simple_test_data()
        print(f"✅ 创建测试数据: {len(test_data)} 条记录")
        
        # 创建技术数据对象
        technical_data = TechnicalIndicators.from_kline_data(test_data)
        print("✅ 创建技术数据对象成功")
        
        # 获取基础数据
        prices = technical_data.prices
        print(f"✅ 获取价格数据: {len(prices)} 个价格点")
        print(f"    价格范围: {prices[0]:.2f} - {prices[-1]:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 基本功能测试失败: {e}")
        traceback.print_exc()
        return False

def test_individual_indicators():
    """测试单个指标"""
    print("\n🧮 测试单个指标...")
    
    try:
        from analysis.technical_indicators import TechnicalIndicators
        
        # 创建测试数据
        test_data = create_simple_test_data()
        technical_data = TechnicalIndicators.from_kline_data(test_data)
        prices = technical_data.prices
        
        # 测试RSI
        print("📊 测试RSI...")
        try:
            rsi = TechnicalIndicators.rsi(prices, 14)
            print(f"✅ RSI计算成功: 长度={len(rsi)}, 最后值={rsi[-1]:.2f}")
        except Exception as e:
            print(f"❌ RSI计算失败: {e}")
            traceback.print_exc()
        
        # 测试MACD
        print("📊 测试MACD...")
        try:
            macd_data = TechnicalIndicators.macd(prices, 12, 26, 9)
            print(f"✅ MACD计算成功")
            print(f"    MACD: {macd_data['macd'][-1]:.4f}")
            print(f"    Signal: {macd_data['signal'][-1]:.4f}")
        except Exception as e:
            print(f"❌ MACD计算失败: {e}")
            traceback.print_exc()
        
        # 测试移动平均线
        print("📊 测试移动平均线...")
        try:
            ma_data = TechnicalIndicators.moving_averages(prices, [5, 20])
            print(f"✅ MA计算成功")
            print(f"    MA5: {ma_data['ma_5'][-1]:.2f}")
            print(f"    MA20: {ma_data['ma_20'][-1]:.2f}")
        except Exception as e:
            print(f"❌ MA计算失败: {e}")
            traceback.print_exc()
        
        return True
        
    except Exception as e:
        print(f"❌ 单个指标测试失败: {e}")
        traceback.print_exc()
        return False

def test_comprehensive_analysis():
    """测试综合分析"""
    print("\n🎯 测试综合分析...")
    
    try:
        from analysis.technical_indicators import TechnicalIndicators
        
        # 创建测试数据
        test_data = create_simple_test_data()
        technical_data = TechnicalIndicators.from_kline_data(test_data)
        
        # 测试综合分析
        print("🧮 计算所有指标...")
        indicators = technical_data.calculate_all_indicators()
        
        print("✅ 综合分析成功!")
        print("📋 结果结构:")
        for category, data in indicators.items():
            if isinstance(data, dict):
                print(f"  - {category}: {len(data)} 个指标")
            else:
                print(f"  - {category}: {type(data)}")
        
        # 测试信号分析
        if "momentum_indicators" in indicators and "rsi" in indicators["momentum_indicators"]:
            rsi_info = indicators["momentum_indicators"]["rsi"]
            print(f"📊 RSI信号: {rsi_info.get('signal', 'N/A')}")
        
        if "trend_indicators" in indicators and "macd" in indicators["trend_indicators"]:
            macd_info = indicators["trend_indicators"]["macd"]
            print(f"📊 MACD信号: {macd_info.get('signal', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 综合分析失败: {e}")
        traceback.print_exc()
        return False

def run_debug_test():
    """运行调试测试"""
    print("🔍 启动技术分析调试测试...")
    print("=" * 50)
    
    tests = [
        test_basic_functionality,
        test_individual_indicators, 
        test_comprehensive_analysis
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("⚠️  测试失败")
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print(f"🎯 调试测试结果: {passed}/{total}")
    
    if passed == total:
        print("✅ 所有调试测试通过!")
        return True
    else:
        print("❌ 存在调试测试失败!")
        return False

if __name__ == "__main__":
    success = run_debug_test()
    exit(0 if success else 1) 