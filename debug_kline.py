#!/usr/bin/env python3
"""
调试历史K线获取问题
"""

import asyncio
import futu as ft
from models.futu_models import HistoryKLineRequest, KLType, AuType
from services.futu_service import FutuService
from loguru import logger

async def test_direct_futu_api():
    """直接测试富途API"""
    logger.info("=== 直接测试富途API ===")
    
    try:
        quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
        
        # 测试基本连接
        ret, data = quote_ctx.get_global_state()
        logger.info(f"连接状态: ret={ret}, data={data}")
        
        if ret != ft.RET_OK:
            logger.error("富途OpenD连接失败")
            return
        
        # 测试获取历史K线
        logger.info("测试获取历史K线...")
        
        code = "HK.09660"
        ktype = ft.KLType.K_5M
        max_count = 10
        
        logger.info(f"参数: code={code}, ktype={ktype}, max_count={max_count}")
        
        ret, data, page_req_key = quote_ctx.request_history_kline(
            code=code,
            start=None,
            end=None,
            ktype=ktype,
            autype=ft.AuType.QFQ,
            fields=[ft.KL_FIELD.ALL],
            max_count=max_count
        )
        
        logger.info(f"结果: ret={ret}")
        if ret == ft.RET_OK:
            logger.info(f"数据类型: {type(data)}")
            logger.info(f"数据形状: {data.shape if hasattr(data, 'shape') else 'N/A'}")
            logger.info(f"前几行数据:\n{data.head() if hasattr(data, 'head') else data}")
        else:
            logger.error(f"获取失败: {data}")
        
        quote_ctx.close()
        
    except Exception as e:
        logger.exception(f"直接API测试失败: {e}")

async def test_service_method():
    """测试服务方法"""
    logger.info("=== 测试服务方法 ===")
    
    try:
        futu_service = FutuService()
        
        # 连接
        success = await futu_service.connect()
        logger.info(f"服务连接: {success}")
        
        if not success:
            logger.error("服务连接失败")
            return
        
        # 创建请求
        request = HistoryKLineRequest(
            code="HK.09660",
            ktype=KLType.K_5M,
            max_count=10,
            autype=AuType.QFQ
        )
        
        logger.info(f"请求对象: {request}")
        
        # 调用方法
        result = await futu_service.get_history_kline(request)
        logger.info(f"结果: {result}")
        
        # 断开连接
        await futu_service.disconnect()
        
    except Exception as e:
        logger.exception(f"服务方法测试失败: {e}")

async def main():
    """主函数"""
    logger.info("开始调试历史K线问题...")
    
    # 首先测试直接API
    await test_direct_futu_api()
    
    # 然后测试服务方法
    await test_service_method()
    
    logger.info("调试完成")

if __name__ == "__main__":
    asyncio.run(main()) 