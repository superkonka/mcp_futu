#!/usr/bin/env python3
"""
富途MCP服务增强版 - 彻底修复初始化问题
采用延迟MCP挂载策略，完全解决时序竞争问题
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from contextlib import asynccontextmanager

# 导入原有模块
from services.futu_service import FutuService
from models.futu_models import *
from models.analysis_models import *
from config import settings

# 导入新功能模块  
from cache.cache_manager import DataCacheManager, CacheConfig
from analysis.technical_indicators import TechnicalIndicators, TechnicalData, IndicatorConfig

# 全局变量
futu_service: Optional[FutuService] = None
cache_manager: Optional[DataCacheManager] = None
_server_ready = False
_mcp_mounted = False
_mcp_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 - 不在这里初始化MCP"""
    global futu_service, cache_manager, _server_ready
    
    logger.info("🚀 启动富途服务基础功能...")
    
    try:
        # 初始化缓存管理器
        cache_config = CacheConfig(
            redis_url="redis://localhost:6379",
            sqlite_path="data/futu_cache.db",
            memory_max_size=2000,
            redis_expire_seconds=7200
        )
        cache_manager = DataCacheManager(cache_config)
        logger.info("✅ 缓存管理器初始化成功")
        
        # 初始化富途服务
        futu_service = FutuService()
        futu_service.cache_manager = cache_manager
        
        # 尝试连接富途OpenD
        if await futu_service.connect():
            logger.info("✅ 富途OpenD连接成功")
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
        
        _server_ready = True
        logger.info("✅ 基础服务初始化完成")
        
        # 启动后台任务延迟挂载MCP
        asyncio.create_task(delayed_mcp_mount(app))
            
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        logger.exception("详细错误信息:")
        raise
    finally:
        # 清理资源
        _server_ready = False
        if futu_service:
            await futu_service.disconnect()
        logger.info("🔥 服务已停止")


async def delayed_mcp_mount(app: FastAPI):
    """延迟挂载MCP服务的后台任务"""
    global _mcp_mounted, _mcp_ready
    
    try:
        # 等待服务器完全启动
        logger.info("⏳ 等待服务器完全启动...")
        await asyncio.sleep(5)
        
        if not _server_ready:
            logger.error("❌ 基础服务未就绪，跳过MCP挂载")
            return
        
        # 延迟导入MCP模块，避免启动时的依赖问题
        try:
            from fastapi_mcp import FastApiMCP
            logger.info("🔄 开始延迟挂载MCP服务...")
            
            # 创建MCP服务实例
            mcp = FastApiMCP(
                app,
                name="富途证券增强版MCP服务",
                description="增强版富途证券API服务，集成15+技术指标、智能缓存系统、专业量化分析功能。支持港股、美股、A股实时报价，K线数据，技术分析指标计算，智能缓存优化，交易历史查询等功能。注意：持仓历史需通过历史成交数据计算。"
            )
            
            # 挂载MCP服务
            mcp.mount()
            _mcp_mounted = True
            logger.info("✅ MCP服务成功挂载")
            
            # 额外等待确保MCP完全初始化
            await asyncio.sleep(10)
            _mcp_ready = True
            logger.info("🎉 MCP服务完全就绪，可以接受外部连接")
            
        except Exception as e:
            logger.error(f"❌ MCP挂载失败: {e}")
            logger.exception("MCP挂载详细错误:")
    
    except Exception as e:
        logger.error(f"❌ 延迟挂载任务异常: {e}")


# 创建FastAPI应用
app = FastAPI(
    title="富途 MCP 增强服务",
    description="集成智能缓存、技术分析、形态识别等功能的专业股票分析平台",
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
    """增强的健康检查"""
    cache_stats = await cache_manager.get_cache_stats() if cache_manager else {}
    
    return {
        "status": "healthy" if _server_ready else "starting",
        "futu_connected": _server_ready,
        "cache_available": cache_manager is not None,
        "mcp_mounted": _mcp_mounted,
        "mcp_ready": _mcp_ready,
        "timestamp": datetime.now().isoformat(),
        "cache_stats": cache_stats,
        "initialization_status": {
            "server_ready": _server_ready,
            "mcp_mounted": _mcp_mounted,
            "mcp_ready": _mcp_ready
        }
    }


# ==================== MCP状态检查接口 ====================
@app.get("/mcp/status")
async def mcp_status_check():
    """专门的MCP状态检查接口"""
    return {
        "mcp_mounted": _mcp_mounted,
        "mcp_ready": _mcp_ready,
        "can_accept_connections": _mcp_ready,
        "timestamp": datetime.now().isoformat(),
        "message": "MCP服务就绪" if _mcp_ready else "MCP服务正在初始化中，请稍候"
    }


# ==================== 手动MCP挂载接口 ====================
@app.post("/admin/mount_mcp")
async def manual_mount_mcp(background_tasks: BackgroundTasks):
    """手动触发MCP挂载（管理接口）"""
    global _mcp_mounted, _mcp_ready
    
    if _mcp_mounted:
        return {"message": "MCP已经挂载", "mcp_ready": _mcp_ready}
    
    if not _server_ready:
        raise HTTPException(status_code=503, detail="基础服务未就绪")
    
    # 启动后台挂载任务
    background_tasks.add_task(delayed_mcp_mount, app)
    
    return {
        "message": "MCP挂载任务已启动",
        "estimated_ready_time": "约15秒后",
        "check_url": "/mcp/status"
    }


# ==================== 时间相关接口 ====================
@app.get("/api/time/current",
         operation_id="get_current_time",
         summary="获取当前时间",
         description="获取服务器当前时间，用于LLM理解时间上下文和模糊时间表达")
async def get_current_time() -> Dict[str, Any]:
    """获取当前时间信息，帮助LLM理解模糊时间表达"""
    now = datetime.now()
    
    # 计算一些常用的时间点
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=now.weekday())  # 本周一
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 股市相关时间（港股为例）
    market_open_today = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_today = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # 判断是否在交易时间
    is_trading_hours = False
    if now.weekday() < 5:  # 周一到周五
        morning_session = (now.replace(hour=9, minute=30) <= now <= now.replace(hour=12, minute=0))
        afternoon_session = (now.replace(hour=13, minute=0) <= now <= now.replace(hour=16, minute=0))
        is_trading_hours = morning_session or afternoon_session
    
    # 生成时间上下文信息
    time_contexts = {
        "今天": today_start.strftime("%Y-%m-%d"),
        "昨天": yesterday_start.strftime("%Y-%m-%d"),
        "本周": week_start.strftime("%Y-%m-%d"),
        "本月": month_start.strftime("%Y-%m-%d"),
        "近期": (now - timedelta(days=7)).strftime("%Y-%m-%d"),  # 最近7天
        "最近": (now - timedelta(days=3)).strftime("%Y-%m-%d"),  # 最近3天
        "这几天": (now - timedelta(days=5)).strftime("%Y-%m-%d"),  # 最近5天
        "上周": (week_start - timedelta(days=7)).strftime("%Y-%m-%d"),
        "上月": (month_start - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d"),
        "最近一个月": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
        "最近三个月": (now - timedelta(days=90)).strftime("%Y-%m-%d")
    }
    
    return {
        "ret_code": 0,
        "ret_msg": "获取当前时间成功",
        "data": {
            # 基础时间信息
            "current_time": now.isoformat(),
            "current_date": now.strftime("%Y-%m-%d"),
            "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": int(now.timestamp()),
            
            # 格式化时间
            "formatted": {
                "iso": now.isoformat(),
                "chinese": now.strftime("%Y年%m月%d日 %H:%M:%S"),
                "date_only": now.strftime("%Y-%m-%d"),
                "time_only": now.strftime("%H:%M:%S"),
                "weekday": now.strftime("%A"),
                "weekday_chinese": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
            },
            
            # 市场时间信息
            "market": {
                "is_trading_day": now.weekday() < 5,
                "is_trading_hours": is_trading_hours,
                "market_open_time": market_open_today.strftime("%H:%M"),
                "market_close_time": market_close_today.strftime("%H:%M"),
                "next_trading_day": _get_next_trading_day(now).strftime("%Y-%m-%d")
            },
            
            # 时间上下文映射（用于模糊时间理解）
            "time_contexts": time_contexts
        }
    }


def _get_next_trading_day(current_time: datetime) -> datetime:
    """计算下一个交易日"""
    next_day = current_time + timedelta(days=1)
    
    # 跳过周末
    while next_day.weekday() >= 5:  # 周六=5, 周日=6
        next_day += timedelta(days=1)
    
    return next_day


# ==================== 股票数据接口 ====================
@app.post("/api/quote/stock_quote",
          operation_id="get_stock_quote_enhanced", 
          summary="获取股票报价（缓存增强）")
async def get_stock_quote_enhanced(request: StockQuoteRequest) -> APIResponse:
    """获取股票报价（缓存增强版）"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # 1. 尝试从缓存获取
        if cache_manager:
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
        if result.ret_code == 0 and cache_manager and result.data.get("quotes"):
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


@app.post("/api/quote/history_kline",
          operation_id="get_history_kline_enhanced",
          summary="获取历史K线（缓存增强）",
          description="智能缓存的历史K线获取，自动从缓存优化数据获取速度")
async def get_history_kline_enhanced(request: HistoryKLineRequest) -> APIResponse:
    """获取历史K线数据（缓存增强版）"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # 1. 尝试从缓存获取数据
        if cache_manager:
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
        if result.ret_code == 0 and cache_manager and result.data.get("kline_data"):
            await cache_manager.store_kline_data(
                request.code, request.ktype.value, 
                request.start, request.end, 
                result.data["kline_data"]
            )
        
        execution_time = time.time() - start_time
        if result.ret_code == 0 and result.data:
            result.data.update({
                "cache_hit": cache_hit,
                "execution_time": execution_time
            })
        
        return result
        
    except Exception as e:
        logger.exception(f"获取历史K线失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取历史K线异常: {e}", data=None)


if __name__ == "__main__":
    logger.info("🚀 启动富途MCP增强服务（彻底修复版）...")
    
    uvicorn.run(
        "main_enhanced_fixed_v2:app",
        host="0.0.0.0",
        port=8001,
        reload=False,  # 关闭reload避免初始化问题
        log_level="info"
    ) 