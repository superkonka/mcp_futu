#!/usr/bin/env python3
"""
富途MCP服务增强版 - 无MCP依赖版本
专注于提供稳定的HTTP API服务
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from contextlib import asynccontextmanager

# 导入原有模块
from services.futu_service import FutuService
from models.futu_models import *

# 导入新功能模块  
try:
    from cache.cache_manager import DataCacheManager, CacheConfig
    CACHE_AVAILABLE = True
except Exception as e:
    logger.warning(f"缓存模块导入失败: {e}")
    CACHE_AVAILABLE = False

try:
    from analysis.technical_indicators import TechnicalIndicators, TechnicalData, IndicatorConfig
    from models.analysis_models import *
    ANALYSIS_AVAILABLE = True
except Exception as e:
    logger.warning(f"技术分析模块导入失败: {e}")
    ANALYSIS_AVAILABLE = False

# 全局变量
futu_service: Optional[FutuService] = None
cache_manager: Optional[DataCacheManager] = None
_server_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global futu_service, cache_manager, _server_ready
    
    logger.info("🚀 启动富途HTTP API服务（无MCP版本）...")
    
    try:
        # 初始化缓存管理器
        if CACHE_AVAILABLE:
            cache_config = CacheConfig(
                redis_url="redis://localhost:6379",
                sqlite_path="data/futu_cache.db",
                memory_max_size=1000,
                redis_expire_seconds=3600
            )
            cache_manager = DataCacheManager(cache_config)
            logger.info("✅ 缓存管理器初始化成功")
        
        # 初始化富途服务
        futu_service = FutuService()
        
        # 尝试连接富途OpenD
        if await futu_service.connect():
            logger.info("✅ 富途OpenD连接成功")
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
        
        _server_ready = True
        logger.info("✅ HTTP API 服务器初始化完成")
            
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        raise
    finally:
        # 清理资源
        _server_ready = False
        if futu_service:
            await futu_service.disconnect()
        logger.info("🔥 服务已停止")


# 创建FastAPI应用
app = FastAPI(
    title="富途 HTTP API 服务（稳定版）",
    description="提供富途股票数据、技术分析和缓存功能的HTTP API服务",
    version="2.0.1",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 健康检查 ====================
@app.get("/health")
async def health_check():
    """健康检查"""
    cache_stats = await cache_manager.get_cache_stats() if cache_manager else {}
    
    return {
        "status": "healthy" if _server_ready else "degraded",
        "futu_connected": _server_ready,
        "cache_available": cache_manager is not None,
        "analysis_available": ANALYSIS_AVAILABLE,
        "timestamp": datetime.now().isoformat(),
        "cache_stats": cache_stats
    }


# ==================== 股票数据接口 ====================
@app.post("/api/quote/stock_quote")
async def get_stock_quote_enhanced(request: StockQuoteRequest) -> APIResponse:
    """获取股票报价（缓存增强版）"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # 1. 尝试从缓存获取
        if CACHE_AVAILABLE and cache_manager:
            cached_data = await cache_manager.get_quote_data(request.code_list)
            if cached_data:
                cache_hit = True
                execution_time = time.time() - start_time
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"获取股票报价成功（缓存）- 执行时间: {execution_time:.3f}s",
                    data={
                        "quotes": cached_data,
                        "data_count": len(cached_data),
                        "cache_hit": True,
                        "execution_time": execution_time
                    }
                )
        
        # 2. 从API获取
        result = await futu_service.get_stock_quote(request)
        
        # 3. 存储到缓存
        if result.ret_code == 0 and CACHE_AVAILABLE and cache_manager and result.data.get("quotes"):
            await cache_manager.store_quote_data(request.code_list, result.data["quotes"])
        
        execution_time = time.time() - start_time
        if result.ret_code == 0 and result.data:
            result.data.update({
                "cache_hit": cache_hit,
                "execution_time": execution_time
            })
        
        return result
        
    except Exception as e:
        logger.exception(f"获取股票报价失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票报价异常: {e}", data=None)


@app.post("/api/quote/history_kline")
async def get_history_kline_enhanced(request: HistoryKLineRequest) -> APIResponse:
    """获取历史K线数据（缓存增强版）"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # 1. 尝试从缓存获取数据
        if CACHE_AVAILABLE and cache_manager:
            cached_data = await cache_manager.get_kline_data(
                request.code, request.ktype.value, request.start, request.end
            )
            if cached_data:
                cache_hit = True
                logger.info(f"缓存命中: {request.code} {request.ktype.value}")
                
                execution_time = time.time() - start_time
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"获取历史K线成功（缓存）- 执行时间: {execution_time:.3f}s",
                    data={
                        "kline_data": cached_data,
                        "data_count": len(cached_data),
                        "cache_hit": True,
                        "execution_time": execution_time
                    }
                )
        
        # 2. 从API获取数据
        result = await futu_service.get_history_kline(request)
        
        # 3. 存储到缓存
        if result.ret_code == 0 and CACHE_AVAILABLE and cache_manager and result.data.get("kline_data"):
            await cache_manager.store_kline_data(
                request.code, request.ktype.value, 
                request.start, request.end,
                result.data["kline_data"]
            )
        
        execution_time = time.time() - start_time
        
        # 增强返回数据
        if result.ret_code == 0 and result.data:
            result.data.update({
                "cache_hit": cache_hit,
                "execution_time": execution_time,
                "data_source": "futu_api"
            })
            result.ret_msg += f" - 执行时间: {execution_time:.3f}s"
        
        return result
        
    except Exception as e:
        logger.exception(f"获取历史K线失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取历史K线异常: {e}", data=None)


@app.post("/api/quote/stock_basicinfo")
async def get_stock_basicinfo(request: StockBasicInfoRequest) -> APIResponse:
    """获取股票基本信息"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_stock_basicinfo(request)
    except Exception as e:
        logger.error(f"获取股票基本信息失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票基本信息失败: {e}", data=None)


# ==================== 技术分析接口 ====================
if ANALYSIS_AVAILABLE:
    @app.post("/api/analysis/simple")
    async def get_simple_analysis(request: Dict):
        """简化的技术分析接口"""
        try:
            code = request.get("code", "HK.00700")
            period = request.get("period", 30)
            
            # 获取K线数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=period)).strftime('%Y-%m-%d')
            
            kline_request = HistoryKLineRequest(
                code=code,
                start=start_date,
                end=end_date,
                ktype="K_DAY",
                max_count=period
            )
            
            # 从富途服务获取数据
            kline_result = await futu_service.get_history_kline(kline_request)
            
            if kline_result.ret_code != 0:
                return {
                    "ret_code": kline_result.ret_code,
                    "ret_msg": f"获取K线数据失败: {kline_result.ret_msg}",
                    "data": None
                }
            
            kline_data = kline_result.data.get("kline_data", [])
            if not kline_data:
                return {
                    "ret_code": -1,
                    "ret_msg": "K线数据为空",
                    "data": None
                }
            
            # 简单的技术分析
            prices = [float(k['close']) for k in kline_data if 'close' in k]
            if len(prices) < 20:
                return {
                    "ret_code": -1,
                    "ret_msg": "数据点不足，无法计算技术指标",
                    "data": None
                }
            
            # 计算简单移动平均线
            ma5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else None
            ma20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else None
            
            # 简单RSI计算
            def calculate_simple_rsi(prices, period=14):
                if len(prices) < period + 1:
                    return None
                
                deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                gains = [d if d > 0 else 0 for d in deltas[-period:]]
                losses = [-d if d < 0 else 0 for d in deltas[-period:]]
                
                avg_gain = sum(gains) / period
                avg_loss = sum(losses) / period
                
                if avg_loss == 0:
                    return 100
                
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                return rsi
            
            rsi = calculate_simple_rsi(prices)
            
            # 简单信号判断
            signal = "中性"
            if ma5 and ma20 and rsi:
                if ma5 > ma20 and rsi < 70:
                    signal = "看涨"
                elif ma5 < ma20 and rsi > 30:
                    signal = "看跌"
            
            return {
                "ret_code": 0,
                "ret_msg": "技术分析计算成功",
                "data": {
                    "code": code,
                    "current_price": prices[-1],
                    "ma5": round(ma5, 2) if ma5 else None,
                    "ma20": round(ma20, 2) if ma20 else None,
                    "rsi": round(rsi, 2) if rsi else None,
                    "signal": signal,
                    "data_points": len(prices),
                    "period": period
                }
            }
            
        except Exception as e:
            logger.exception(f"技术分析失败: {e}")
            return {
                "ret_code": -1,
                "ret_msg": f"技术分析异常: {e}",
                "data": None
            }


# ==================== 缓存管理接口 ====================
if CACHE_AVAILABLE:
    @app.get("/api/cache/status")
    async def get_cache_status(detailed: bool = False):
        """获取缓存状态"""
        if not cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        try:
            stats = await cache_manager.get_cache_stats()
            return {
                "ret_code": 0,
                "ret_msg": "缓存状态获取成功",
                "data": stats if detailed else {
                    "memory_cache_size": stats.get("memory_cache_size", 0),
                    "redis_available": stats.get("redis_available", False),
                    "sqlite_available": stats.get("sqlite_available", False)
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.exception(f"获取缓存状态失败: {e}")
            return {
                "ret_code": -1,
                "ret_msg": f"获取缓存状态异常: {e}",
                "data": None
            }


# ==================== 工具信息接口 ====================
@app.get("/api/tools/list")
async def list_available_tools():
    """列出可用的工具和接口"""
    tools = [
        {
            "name": "get_stock_quote",
            "path": "/api/quote/stock_quote",
            "method": "POST",
            "description": "获取股票实时报价",
            "category": "stock_data"
        },
        {
            "name": "get_history_kline",
            "path": "/api/quote/history_kline", 
            "method": "POST",
            "description": "获取历史K线数据",
            "category": "stock_data"
        },
        {
            "name": "get_stock_basicinfo",
            "path": "/api/quote/stock_basicinfo",
            "method": "POST", 
            "description": "获取股票基本信息",
            "category": "stock_data"
        }
    ]
    
    if ANALYSIS_AVAILABLE:
        tools.append({
            "name": "get_simple_analysis",
            "path": "/api/analysis/simple",
            "method": "POST",
            "description": "获取简化技术分析",
            "category": "technical_analysis"
        })
    
    if CACHE_AVAILABLE:
        tools.append({
            "name": "get_cache_status",
            "path": "/api/cache/status",
            "method": "GET",
            "description": "获取缓存状态",
            "category": "cache_management"
        })
    
    return {
        "ret_code": 0,
        "ret_msg": "工具列表获取成功",
        "data": {
            "tools": tools,
            "total_count": len(tools),
            "categories": list(set([tool["category"] for tool in tools])),
            "server_features": {
                "cache_available": CACHE_AVAILABLE,
                "analysis_available": ANALYSIS_AVAILABLE,
                "futu_connected": _server_ready
            }
        }
    }


if __name__ == "__main__":
    logger.info("🚀 启动富途HTTP API服务...")
    
    uvicorn.run(
        "main_enhanced_simple_alternative:app",
        host="0.0.0.0",
        port=8002,  # 使用不同端口避免冲突
        reload=False,  # 生产模式
        log_level="info"
    ) 