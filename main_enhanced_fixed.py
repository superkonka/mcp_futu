#!/usr/bin/env python3
"""
富途MCP服务增强版 - 修复初始化问题
采用延迟初始化策略解决MCP服务器时序问题
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as log
from contextlib import asynccontextmanager
from futu import *
from fastapi_mcp import FastApiMCP

# Ensure we use loguru logger after futu import
logger = log

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
_mcp_initialized = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global futu_service, cache_manager, _server_ready
    
    logger.info("🚀 启动增强版MCP Futu服务...")
    
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
        # 设置缓存管理器
        futu_service.cache_manager = cache_manager
        
        # 尝试连接富途OpenD
        if await futu_service.connect():
            logger.info("✅ 富途OpenD连接成功")
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
        
        _server_ready = True
        logger.info("✅ 增强版服务器初始化完成")
            
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


# 创建FastAPI应用
app = FastAPI(
    title="富途 MCP 增强服务",
    description="集成智能缓存、技术分析、形态识别等功能的专业股票分析平台",
    version="2.0.0",
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
    """健康检查接口"""
    return {
        "status": "healthy" if _server_ready else "initializing",
        "timestamp": datetime.now().isoformat(),
        "futu_connected": futu_service.is_connected() if futu_service else False,
        "cache_enabled": cache_manager is not None,
        "mcp_ready": _mcp_initialized
    }


# ==================== 延迟MCP初始化 ====================

async def initialize_mcp_delayed():
    """延迟初始化MCP服务"""
    global _mcp_initialized
    
    if _mcp_initialized:
        return
    
    try:
        # 等待服务器完全启动
        await asyncio.sleep(5)
        
        if not _server_ready:
            logger.warning("服务器未就绪，跳过MCP初始化")
            return
        
        logger.info("🔄 开始延迟初始化MCP服务...")
        
        # 创建并配置MCP服务
        mcp = FastApiMCP(
            app,
            name="富途证券增强版MCP服务",
            description="增强版富途证券API服务，集成15+技术指标、智能缓存系统、专业量化分析功能。支持港股、美股、A股实时报价，K线数据，技术分析指标计算，智能缓存优化，交易历史查询等功能。注意：持仓历史需通过历史成交数据计算。"
        )
        
        # 挂载MCP服务到FastAPI应用
        mcp.mount()
        
        _mcp_initialized = True
        logger.info("✅ MCP服务延迟初始化完成")
        
    except Exception as e:
        logger.error(f"❌ MCP延迟初始化失败: {e}")
        logger.exception("详细错误信息:")


# 在应用启动后异步初始化MCP
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 创建后台任务来延迟初始化MCP
    asyncio.create_task(initialize_mcp_delayed())


# ==================== 基础API接口 ====================
# 这里添加所有原有的API接口...
# (为了简洁，这里省略具体接口实现，可以从原文件复制)

if __name__ == "__main__":
    logger.info("🚀 启动富途MCP增强服务...")
    
    uvicorn.run(
        "main_enhanced_fixed:app",
        host="0.0.0.0",
        port=8001,
        reload=False,  # 关闭reload避免初始化问题
        log_level="info"
    )