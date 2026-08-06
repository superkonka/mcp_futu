#!/usr/bin/env python3
"""
测试优化后的 get_stock_basicinfo 方法
"""

import asyncio
import json
import sys
from services.futu_service import FutuService
from models.futu_models import StockBasicInfoRequest, Market, SecurityType, DataOptimization
from loguru import logger

async def test_optimized_stock_basicinfo():
    """测试优化后的股票基本信息获取"""
    logger.info("=== 测试优化后的股票基本信息获取 ===")
    
    futu_service = FutuService()
    
    try:
        # 连接富途API
        connected = await futu_service.connect()
        if not connected:
            logger.error("无法连接到富途OpenD")
            return
        
        # 测试1: 数量限制 + 字段优化
        logger.info("\n--- 测试1: 启用所有优化（数量限制+字段过滤） ---")
        optimized_request = StockBasicInfoRequest(
            market=Market.HK,
            stock_type=SecurityType.STOCK,
            max_count=50,  # 限制只返回50只股票
            optimization=DataOptimization(
                enable_optimization=True,
                only_essential_fields=True,
                remove_meaningless_values=True
            )
        )
        
        result = await futu_service.get_stock_basicinfo(optimized_request)
        
        if result.ret_code == 0:
            data_count = result.data.get("data_count", 0)
            total_available = result.data.get("total_available", 0)
            logger.info(f"返回股票数量: {data_count}")
            logger.info(f"可用股票总数: {total_available}")
            logger.info(f"返回消息: {result.ret_msg}")
            
            if result.data.get("basic_info"):
                first_stock = result.data["basic_info"][0]
                logger.info(f"第一只股票的字段数量: {len(first_stock)}")
                logger.info(f"第一只股票的字段: {list(first_stock.keys())}")
                logger.info(f"第一只股票的详细信息: {json.dumps(first_stock, indent=2, ensure_ascii=False)}")
                
                # 计算数据大小
                json_str = json.dumps(result.data, ensure_ascii=False)
                data_size = len(json_str.encode('utf-8'))
                logger.info(f"优化后数据大小: {data_size} bytes ({data_size/1024:.2f} KB)")
        else:
            logger.error(f"获取失败: {result.ret_msg}")
        
        # 测试2: 自定义字段
        logger.info("\n--- 测试2: 自定义字段优化 ---")
        custom_request = StockBasicInfoRequest(
            market=Market.HK,
            stock_type=SecurityType.STOCK,
            max_count=20,  # 只返回20只股票
            optimization=DataOptimization(
                enable_optimization=True,
                custom_fields=['code', 'name', 'lot_size'],  # 只返回这三个字段
                remove_meaningless_values=True
            )
        )
        
        result_custom = await futu_service.get_stock_basicinfo(custom_request)
        
        if result_custom.ret_code == 0:
            data_count = result_custom.data.get("data_count", 0)
            logger.info(f"自定义字段返回股票数量: {data_count}")
            
            if result_custom.data.get("basic_info"):
                first_stock = result_custom.data["basic_info"][0]
                logger.info(f"自定义字段第一只股票: {json.dumps(first_stock, indent=2, ensure_ascii=False)}")
                
                # 计算数据大小
                json_str = json.dumps(result_custom.data, ensure_ascii=False)
                data_size = len(json_str.encode('utf-8'))
                logger.info(f"自定义字段数据大小: {data_size} bytes ({data_size/1024:.2f} KB)")
        else:
            logger.error(f"自定义字段获取失败: {result_custom.ret_msg}")
        
        # 测试3: 极简模式 - 仅获取前10只股票的基本信息
        logger.info("\n--- 测试3: 极简模式（仅10只股票） ---")
        minimal_request = StockBasicInfoRequest(
            market=Market.HK,
            stock_type=SecurityType.STOCK,
            max_count=10,
            optimization=DataOptimization(
                enable_optimization=True,
                custom_fields=['code', 'name']  # 只要代码和名称
            )
        )
        
        result_minimal = await futu_service.get_stock_basicinfo(minimal_request)
        
        if result_minimal.ret_code == 0:
            logger.info(f"极简模式返回: {json.dumps(result_minimal.data, indent=2, ensure_ascii=False)}")
            
            # 计算数据大小
            json_str = json.dumps(result_minimal.data, ensure_ascii=False)
            data_size = len(json_str.encode('utf-8'))
            logger.info(f"极简模式数据大小: {data_size} bytes ({data_size/1024:.2f} KB)")
        else:
            logger.error(f"极简模式获取失败: {result_minimal.ret_msg}")
        
    except Exception as e:
        logger.exception(f"测试异常: {e}")
    finally:
        await futu_service.disconnect()

if __name__ == "__main__":
    asyncio.run(test_optimized_stock_basicinfo()) 