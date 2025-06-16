#!/usr/bin/env python3
"""测试修复后的get_history_kline功能"""

import asyncio
import sys
from services.futu_service import FutuService
from models.futu_models import HistoryKLineRequest, KLType, AuType


async def test_history_kline():
    """测试历史K线功能"""
    futu_service = FutuService()
    
    # 连接富途OpenD
    connected = await futu_service.connect()
    if not connected:
        print("❌ 无法连接到富途OpenD")
        return False
    
    print("✅ 富途OpenD连接成功")
    
    # 测试用例1：基本请求
    print("\n📊 测试1: 获取腾讯(HK.00700)日K线...")
    request1 = HistoryKLineRequest(
        code="HK.00700",
        ktype=KLType.K_DAY,
        autype=AuType.QFQ,
        max_count=10  # 只获取10条数据
    )
    
    try:
        result1 = await futu_service.get_history_kline(request1)
        if result1.ret_code == 0:
            print(f"✅ 成功获取 {len(result1.data['kline_data'])} 条K线数据")
            if result1.data['kline_data']:
                print(f"📅 最新数据时间: {result1.data['kline_data'][-1]['time_key']}")
        else:
            print(f"❌ 获取失败: {result1.ret_msg}")
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
    
    # 测试用例2：带日期范围的请求
    print("\n📊 测试2: 获取苹果(US.AAPL)指定日期范围的日K线...")
    request2 = HistoryKLineRequest(
        code="US.AAPL",
        start="2024-01-01",
        end="2024-01-31",
        ktype=KLType.K_DAY,
        autype=AuType.QFQ,
        max_count=50
    )
    
    try:
        result2 = await futu_service.get_history_kline(request2)
        if result2.ret_code == 0:
            print(f"✅ 成功获取 {len(result2.data['kline_data'])} 条K线数据")
        else:
            print(f"❌ 获取失败: {result2.ret_msg}")
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
    
    # 断开连接
    await futu_service.disconnect()
    print("\n🔌 已断开富途OpenD连接")
    
    return True


if __name__ == "__main__":
    print("🚀 开始测试历史K线功能修复...")
    asyncio.run(test_history_kline())
    print("✅ 测试完成！") 