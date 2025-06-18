#!/usr/bin/env python3
"""
富途MCP服务增强版 - 简化版本
先确保基本功能正常工作
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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
    
    logger.info("🚀 启动增强版MCP Futu服务（简化版）...")
    
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
            _server_ready = True
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
            
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        raise
    finally:
        # 清理资源
        if futu_service:
            await futu_service.disconnect()
        logger.info("🔥 服务已停止")


# 创建FastAPI应用
app = FastAPI(
    title="富途 MCP 增强服务（简化版）",
    description="测试版本的增强MCP服务",
    version="2.0.0-simple",
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
    return {
        "status": "healthy" if _server_ready else "degraded",
        "futu_connected": _server_ready,
        "cache_available": CACHE_AVAILABLE and cache_manager is not None,
        "analysis_available": ANALYSIS_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }


# ==================== 缓存状态 ====================
@app.get("/api/cache/status")
async def get_cache_status():
    """获取缓存状态"""
    if not CACHE_AVAILABLE or not cache_manager:
        return {
            "ret_code": -1,
            "ret_msg": "缓存管理器不可用",
            "data": None
        }
    
    try:
        stats = await cache_manager.get_cache_stats()
        return {
            "ret_code": 0,
            "ret_msg": "缓存状态获取成功",
            "data": {
                "cache_available": True,
                "stats": stats
            }
        }
    except Exception as e:
        logger.exception(f"获取缓存状态失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"获取缓存状态异常: {e}",
            "data": None
        }


# ==================== 简化的技术分析接口 ====================
@app.post("/api/analysis/simple")
async def get_simple_analysis(request: Dict):
    """简化的技术分析接口"""
    if not ANALYSIS_AVAILABLE:
        return {
            "ret_code": -1,
            "ret_msg": "技术分析模块不可用",
            "data": None
        }
    
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
        
        # 计算简单RSI
        if len(prices) >= 14:
            gains = []
            losses = []
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(-change)
            
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            
            # 修复：防止除零错误
            if avg_loss == 0:
                rsi = 100.0 if avg_gain > 0 else 50.0  # 无损失时RSI为100，无变化时为50
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
        else:
            rsi = None
        
        return {
            "ret_code": 0,
            "ret_msg": "简单技术分析完成",
            "data": {
                "code": code,
                "period": period,
                "data_points": len(prices),
                "current_price": prices[-1] if prices else None,
                "ma5": round(ma5, 2) if ma5 else None,
                "ma20": round(ma20, 2) if ma20 else None,
                "rsi": round(rsi, 2) if rsi else None,
                "signal": "看涨" if ma5 and ma20 and ma5 > ma20 else "看跌" if ma5 and ma20 else "中性"
            }
        }
        
    except Exception as e:
        logger.exception(f"技术分析失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"技术分析异常: {e}",
            "data": None
        }


# ==================== 增强的历史K线接口 ====================
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


# ==================== 原有接口保持兼容 ====================
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


@app.post("/api/quote/stock_quote")
async def get_stock_quote(request: StockQuoteRequest) -> APIResponse:
    """获取股票报价"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_stock_quote(request)
    except Exception as e:
        logger.error(f"获取股票报价失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票报价失败: {e}", data=None)


# ==================== 启动配置 ====================
if __name__ == "__main__":
    logger.info("🚀 启动富途MCP增强服务（简化版）...")
    
    uvicorn.run(
        "main_enhanced_simple:app",
        host="0.0.0.0",
        port=8002,  # 使用不同端口避免冲突
        reload=True,
        log_level="info"
    ) 