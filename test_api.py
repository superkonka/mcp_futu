#!/usr/bin/env python3
"""测试 API 接口"""
import urllib.request
import json

def test_health():
    """测试健康检查"""
    try:
        response = urllib.request.urlopen('http://localhost:8001/health', timeout=5)
        data = json.loads(response.read().decode())
        print("Health Check:")
        print(f"  Status: {data.get('status')}")
        print(f"  Futu Connected: {data.get('futu_connected')}")
        print(f"  Cache Available: {data.get('cache_available')}")
        return True
    except Exception as e:
        print(f"Health Check Error: {e}")
        return False

def test_stock_quote():
    """测试股票报价"""
    try:
        req = urllib.request.Request(
            'http://localhost:8001/api/quote/stock_quote',
            data=json.dumps({'code_list': ['HK.00700']}).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
        print("\nStock Quote (HK.00700):")
        if data.get('data') and data['data'].get('quotes'):
            quote = data['data']['quotes'][0]
            print(f"  Name: {quote.get('stock_name', 'N/A')}")
            print(f"  Price: {quote.get('last_price', 'N/A')}")
            print(f"  Change: {quote.get('change_rate', 'N/A')}%")
            print(f"  Volume: {quote.get('volume', 'N/A')}")
            return True
        else:
            print(f"  Error: {data.get('ret_msg', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"Stock Quote Error: {e}")
        return False

def test_history_kline():
    """测试历史K线"""
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
        print("\nHistory KLine (HK.00700):")
        if data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            print(f"  Retrieved {len(klines)} KLine records")
            if klines:
                latest = klines[-1]
                print(f"  Latest: {latest.get('time_key')} - Close: {latest.get('close')}")
            return True
        else:
            print(f"  Error: {data.get('ret_msg', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"KLine Error: {e}")
        return False

if __name__ == '__main__':
    print("="*60)
    print("  API 测试")
    print("="*60)
    
    results = []
    results.append(('Health Check', test_health()))
    results.append(('Stock Quote', test_stock_quote()))
    results.append(('History KLine', test_history_kline()))
    
    print("\n" + "="*60)
    print("  测试结果")
    print("="*60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
    
    passed_count = sum(1 for _, p in results if p)
    print(f"\n  Total: {passed_count}/{len(results)} passed")
