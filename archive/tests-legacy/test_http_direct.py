#!/usr/bin/env python3
"""
直接测试HTTP接口
"""

import asyncio
import aiohttp
import json
from models.futu_models import HistoryKLineRequest, KLType, AuType
from loguru import logger

async def test_http_endpoint():
    """测试HTTP端点"""
    url = "http://127.0.0.1:8001/api/quote/history_kline"
    
    # 测试数据1：使用字符串值
    test_data_1 = {
        "code": "HK.09660",
        "ktype": "K_5M",
        "autype": "qfq",
        "max_count": 10
    }
    
    # 测试数据2：使用Pydantic模型
    request_model = HistoryKLineRequest(
        code="HK.09660",
        ktype=KLType.K_5M,
        autype=AuType.QFQ,
        max_count=10
    )
    test_data_2 = request_model.model_dump(mode='json')
    
    logger.info(f"测试数据1 (字符串): {test_data_1}")
    logger.info(f"测试数据2 (模型): {test_data_2}")
    
    async with aiohttp.ClientSession() as session:
        # 测试1：字符串数据
        try:
            logger.info("=== 测试1：字符串数据 ===")
            async with session.post(url, json=test_data_1) as response:
                status = response.status
                text = await response.text()
                logger.info(f"状态码: {status}")
                logger.info(f"响应: {text}")
        except Exception as e:
            logger.exception(f"测试1失败: {e}")
        
        # 测试2：模型数据
        try:
            logger.info("=== 测试2：模型数据 ===")
            async with session.post(url, json=test_data_2) as response:
                status = response.status
                text = await response.text()
                logger.info(f"状态码: {status}")
                logger.info(f"响应: {text}")
        except Exception as e:
            logger.exception(f"测试2失败: {e}")
        
        # 测试3：健康检查
        try:
            logger.info("=== 测试3：健康检查 ===")
            async with session.get("http://127.0.0.1:8001/health") as response:
                status = response.status
                data = await response.json()
                logger.info(f"健康检查状态码: {status}")
                logger.info(f"健康检查响应: {data}")
        except Exception as e:
            logger.exception(f"健康检查失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_http_endpoint()) 