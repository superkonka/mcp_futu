#!/usr/bin/env python3
"""
API错误调试脚本
"""

import sys
import os
import requests
import json
import traceback

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_technical_indicators():
    """测试技术指标API"""
    url = "http://localhost:8001/api/analysis/technical_indicators"
    
    payload = {
        "code": "HK.01810",
        "indicators": ["macd", "rsi", "bollinger_bands"],
        "period": 14,
        "ktype": "K_DAY",
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "rsi_period": 14,
        "bollinger_period": 20,
        "optimization": {
            "enable_optimization": True,
            "only_essential_fields": True
        }
    }
    
    try:
        print("🧪 测试技术指标API...")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 500:
            print("❌ 服务器内部错误")
            print(f"响应内容: {response.text}")
        elif response.status_code == 200:
            print("✅ 请求成功")
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"⚠️ 未预期的状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        traceback.print_exc()

def test_simple_analysis():
    """测试简化版分析API作为对比"""
    url = "http://localhost:8002/api/analysis/simple"
    
    payload = {
        "code": "HK.01810",
        "period": 30
    }
    
    try:
        print("\n🧪 测试简化版分析API（对比）...")
        print(f"URL: {url}")
        
        response = requests.post(url, json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 简化版正常工作")
            data = response.json()
            print(f"简化版响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ 简化版也有问题: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 简化版请求异常: {e}")

def test_imports():
    """测试导入是否正常"""
    try:
        print("\n🧪 测试模块导入...")
        
        from models.analysis_models import TechnicalAnalysisRequest, EnhancedAPIResponse
        print("✅ analysis_models 导入成功")
        
        from analysis.technical_indicators import TechnicalIndicators
        print("✅ technical_indicators 导入成功")
        
        # 测试创建请求对象
        request = TechnicalAnalysisRequest(
            code="HK.01810",
            indicators=["macd", "rsi"],
            period=14
        )
        print("✅ TechnicalAnalysisRequest 创建成功")
        print(f"请求对象: {request.dict()}")
        
    except Exception as e:
        print(f"❌ 导入测试失败: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("🔍 启动API错误调试...")
    print("=" * 50)
    
    test_imports()
    test_technical_indicators()
    test_simple_analysis()
    
    print("\n" + "=" * 50)
    print("🎯 调试完成") 