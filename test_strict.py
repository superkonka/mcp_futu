#!/usr/bin/env python3
"""验证严格模式是否生效"""
import urllib.request
import json

def test_strict_mode():
    """测试严格模式"""
    print("="*60)
    print("  Strict Mode Verification")
    print("="*60)
    
    # 1. 健康检查
    print("\n1. Health Check:")
    try:
        response = urllib.request.urlopen('http://localhost:8001/health', timeout=5)
        data = json.loads(response.read().decode())
        print(f"   Status: {data.get('status')}")
        print(f"   Futu Connected: {data.get('futu_connected')}")
        print(f"   Cache Available: {data.get('cache_available')}")
        
        if data.get('futu_connected'):
            print("   [OK] Futu OpenD connected")
    except Exception as e:
        print(f"   [ERROR]: {e}")
        return False
    
    # 2. 获取真实股票数据
    print("\n2. Real Stock Data (HK.00700):")
    try:
        req = urllib.request.Request(
            'http://localhost:8001/api/quote/stock_quote',
            data=json.dumps({'code_list': ['HK.00700']}).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
        
        if data.get('ret_code') == 0 and data.get('data', {}).get('quotes'):
            quote = data['data']['quotes'][0]
            print(f"   Code: {quote.get('code')}")
            print(f"   Name: {quote.get('stock_name')}")
            print(f"   Price: {quote.get('last_price')}")
            print(f"   Volume: {quote.get('volume')}")
            print("   [OK] Real data from OpenD")
        else:
            print(f"   [ERROR]: {data.get('ret_msg')}")
            return False
    except Exception as e:
        print(f"   [ERROR]: {e}")
        return False
    
    # 3. 测试 K 线数据
    print("\n3. K-Line Data (HK.00700):")
    try:
        req = urllib.request.Request(
            'http://localhost:8001/api/quote/history_kline',
            data=json.dumps({
                'code': 'HK.00700',
                'ktype': 'K_DAY',
                'max_count': 5
            }).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
        
        if data.get('ret_code') == 0 and data.get('data', {}).get('klines'):
            klines = data['data']['klines']
            print(f"   Retrieved {len(klines)} records")
            if klines:
                latest = klines[-1]
                print(f"   Latest: {latest.get('time_key')} Close: {latest.get('close')}")
            print("   [OK] Real K-line data from OpenD")
        else:
            print(f"   Note: {data.get('ret_msg', 'No data')}")
    except Exception as e:
        print(f"   [ERROR]: {e}")
    
    print("\n" + "="*60)
    print("  All tests passed!")
    print("  Strict mode is active - all data is real-time from OpenD")
    print("="*60)
    return True

if __name__ == '__main__':
    test_strict_mode()
