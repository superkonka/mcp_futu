#!/usr/bin/env python3

import requests
import json

print("🔍 检查服务器状态...")

# 健康检查
try:
    health_response = requests.get("http://localhost:8001/health", timeout=5)
    if health_response.status_code == 200:
        health_data = health_response.json()
        print("✅ 健康检查:")
        print(f"  - 状态: {health_data.get('status')}")
        print(f"  - futu_connected: {health_data.get('futu_connected')}")
        print(f"  - cache_available: {health_data.get('cache_available')}")
    else:
        print(f"❌ 健康检查失败: {health_response.status_code}")
except Exception as e:
    print(f"❌ 健康检查异常: {e}")

# K线测试
print("\n🧪 测试K线API...")
kline_payload = {
    "code": "HK.01810",
    "start": "2025-06-01", 
    "end": "2025-06-17",
    "ktype": "K_DAY",
    "max_count": 30
}

try:
    kline_response = requests.post(
        "http://localhost:8001/api/quote/history_kline",
        json=kline_payload,
        timeout=10
    )
    print(f"K线API状态码: {kline_response.status_code}")
    
    if kline_response.status_code == 200:
        kline_data = kline_response.json()
        print(f"✅ K线API返回:")
        print(f"  - ret_code: {kline_data.get('ret_code')}")
        print(f"  - ret_msg: {kline_data.get('ret_msg')}")
    else:
        print(f"❌ K线API错误: {kline_response.text}")
        
except Exception as e:
    print(f"❌ K线API异常: {e}") 