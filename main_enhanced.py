#!/usr/bin/env python3
"""
富途MCP服务增强版 - 集成缓存和技术分析功能
支持智能缓存、技术指标计算、形态识别等高级功能
"""

import asyncio
import time
import secrets
import json
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone, time as dtime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from collections import defaultdict
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as log  # Use alias to avoid conflicts
from contextlib import asynccontextmanager
from futu import *
from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

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
# 导入基本面搜索服务
from services.fundamental_service import fundamental_service
from models.fundamental_models import FundamentalSearchRequest, FundamentalSearchResponse
from services.recommendation_storage import RecommendationStorageService
from models.recommendation_models import RecommendationWriteRequest, RecommendationQueryRequest, RecommendationUpdateRequest, RecommendationReevaluateRequest
from models.dashboard_models import DashboardSessionRequest, DashboardSessionResponse, DashboardSessionItem
from services.dashboard_stream import DashboardStreamManager
from services.dashboard_session_store import DashboardSessionStore
from services.deepseek_service import DeepSeekService
from services.fundamental_storage import FundamentalNewsStorage
from services.minute_kline_storage import MinuteKlineStorage
from services.multi_model_service import MultiModelAnalysisService
from services.strategy_monitor import StrategyMonitorService

# 全局变量
futu_service: Optional[FutuService] = None
cache_manager: Optional[DataCacheManager] = None
recommendation_storage: Optional[RecommendationStorageService] = None
deepseek_service: Optional[DeepSeekService] = None
fundamental_storage: Optional[FundamentalNewsStorage] = None
_server_ready = False
dashboard_sessions: Dict[str, Dict[str, Any]] = {}
_dashboard_lock = asyncio.Lock()
dashboard_stream_manager: Optional[DashboardStreamManager] = None
dashboard_session_store: Optional[DashboardSessionStore] = None
minute_kline_storage: Optional[MinuteKlineStorage] = None
multi_model_service: Optional[MultiModelAnalysisService] = None
strategy_monitor: Optional[StrategyMonitorService] = None
DASHBOARD_DIST_PATH = Path("web/dashboard-app/dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global futu_service, cache_manager, recommendation_storage, dashboard_stream_manager, dashboard_session_store, _server_ready, deepseek_service, fundamental_storage, minute_kline_storage, multi_model_service, strategy_monitor
    
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
        
        recommendation_storage = RecommendationStorageService(db_path="data/recommendations.db")
        logger.info("✅ 策略建议存储服务初始化成功")
        dashboard_session_store = DashboardSessionStore(path="data/dashboard_sessions.json")
        logger.info("✅ 看板会话存储初始化成功")
        fundamental_storage = FundamentalNewsStorage(db_path="data/fundamental_news.db")
        logger.info("✅ 基本面资讯存储初始化成功")
        minute_kline_storage = MinuteKlineStorage(db_path="data/minute_kline.db")
        logger.info("✅ 分钟级K线存储初始化成功")
        if settings.deepseek_api_key:
            # 如果使用 Speciale base_url 且未指定模型，自动使用 special 模型名
            base_url = settings.deepseek_base_url or "https://api.deepseek.com/v1/chat/completions"
            is_speciale = "speciale" in (base_url or "").lower()
            default_model = "deepseek-v3.2-speciale" if is_speciale else "deepseek-v3.2"
            default_fundamental_model = default_model
            deepseek_service = DeepSeekService(
                settings.deepseek_api_key,
                base_url=base_url,
                model=settings.deepseek_model or default_model,
                fundamental_model=settings.deepseek_fundamental_model or default_fundamental_model,
            )
            logger.info("✅ DeepSeek分析服务已启用")
        else:
            logger.warning("⚠️ DeepSeek API KEY 未配置，基本面高级分析不可用")
        multi_model_service = MultiModelAnalysisService(deepseek_service)
        
        # 初始化富途服务
        futu_service = FutuService()
        # 设置缓存管理器
        futu_service.cache_manager = cache_manager

        # 本地密钥检查（不影响服务启动，但提醒用户）
        if not settings.metaso_api_key:
            logger.warning("⚠️ Metaso API 密钥未配置。本地使用请在 .env 设置 METASO_API_KEY。")
        if not (settings.kimi_moonshot_key or settings.kimi_api_key):
            logger.warning("⚠️ Kimi API 密钥未配置。本地使用请在 .env 设置 KIMI_MOONSHOT_KEY。")
        
        # 尝试连接富途OpenD
        if await futu_service.connect():
            logger.info("✅ 富途OpenD连接成功")
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
        
        if dashboard_session_store:
            loaded_sessions = await asyncio.to_thread(dashboard_session_store.load)
            async with _dashboard_lock:
                for session_id, info in loaded_sessions.items():
                    info.setdefault("history", [])
                    dashboard_sessions[session_id] = info
            logger.info(f"✅ 已恢复 {len(loaded_sessions)} 个看板会话")
        
        try:
            loop = asyncio.get_running_loop()
            dashboard_stream_manager = DashboardStreamManager(futu_service, loop, minute_kline_storage)
            if dashboard_sessions:
                for session_id, info in dashboard_sessions.items():
                    code = info.get("code")
                    if code:
                        dashboard_stream_manager.register_session(session_id, code)
                unique_codes = {sess["code"] for sess in dashboard_sessions.values() if sess.get("code")}
                for code in unique_codes:
                    await dashboard_stream_manager.ensure_code_subscription(code)
            dashboard_stream_manager.start_guard()
        except RuntimeError:
            logger.warning("未获取到事件循环，dashboard流功能不可用")
        
        strategy_monitor = StrategyMonitorService(futu_service, recommendation_storage)
        await strategy_monitor.start()

        # 等待服务完全初始化
        await asyncio.sleep(3)
        
        _server_ready = True
        logger.info("✅ Web API 服务初始化完成 (MCP 已拆分为独立进程)")
        if settings.external_mcp_endpoint:
            logger.info(f"📡 外部 MCP 访问地址: {settings.external_mcp_endpoint}")
            
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
        if strategy_monitor:
            await strategy_monitor.stop()
        minute_kline_storage = None
        logger.info("🔥 服务已停止")


# 创建FastAPI应用
app = FastAPI(
    title="富途 MCP 增强服务",
    description="集成智能缓存、技术分析、形态识别等功能的专业股票分析平台",
    version="2.0.0",
    lifespan=lifespan
)

if DASHBOARD_DIST_PATH.exists():
    app.mount("/assets", StaticFiles(directory=DASHBOARD_DIST_PATH / "assets"), name="dashboard_assets")
    if (DASHBOARD_DIST_PATH / "vite.svg").exists():
        app.mount("/vite.svg", StaticFiles(directory=DASHBOARD_DIST_PATH), name="dashboard_vite")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/web/dashboard", include_in_schema=False)
async def dashboard_page():
    """返回前端仪表板页面"""
    if DASHBOARD_DIST_PATH.exists():
        dist_index = DASHBOARD_DIST_PATH / "index.html"
        if dist_index.exists():
            return FileResponse(dist_index)
    file_path = Path("web/dashboard.html")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="dashboard page not found")
    return FileResponse(file_path)


@app.get("/web", include_in_schema=False)
async def dashboard_home():
    """可视化首页"""
    if DASHBOARD_DIST_PATH.exists():
        dist_index = DASHBOARD_DIST_PATH / "index.html"
        if dist_index.exists():
            return FileResponse(dist_index)
    file_path = Path("web/index.html")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="home page not found")
    return FileResponse(file_path)

# ==================== 启动事件处理 ====================
@app.on_event("startup")
async def startup_event():
    """应用启动事件 - 确保MCP完全初始化"""
    global _server_ready
    
    # 等待额外的初始化时间
    await asyncio.sleep(2)
    
    if not _server_ready:
        logger.warning("⚠️  服务器初始化延迟，请稍后重试连接")
    else:
        logger.info("✅ Web API 服务已就绪")


# ==================== 健康检查 ====================
@app.get("/health")
async def health_check():
    """健康检查"""
    cache_stats = await cache_manager.get_cache_stats() if cache_manager else {}
    
    return {
        "status": "healthy" if _server_ready else "degraded",
        "futu_connected": _server_ready,
        "cache_available": cache_manager is not None,
        "mcp_proxy": {
            "mode": "external",
            "endpoint": settings.external_mcp_endpoint
        },
        "metaso_configured": settings.metaso_api_key is not None,
        "kimi_configured": settings.kimi_api_key is not None,
        "timestamp": datetime.now().isoformat(),
        "cache_stats": cache_stats
    }

@app.get("/mcp/status")
async def mcp_status():
    """MCP状态检查：让客户端在连接前确认就绪"""
    ready = settings.external_mcp_endpoint is not None
    return {
        "mcp_ready": ready,
        "server_ready": _server_ready,
        "mode": "external",
        "external_endpoint": settings.external_mcp_endpoint,
        "can_accept_connections": ready,
        "timestamp": datetime.now().isoformat(),
        "message": "MCP服务已拆分为独立进程，请直接连接 external_endpoint"
    }


@app.api_route("/mcp{extra_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
async def mcp_redirect(extra_path: str, request: Request):
    """将旧的 /mcp 请求重定向到独立的 MCP 服务"""
    if not settings.external_mcp_endpoint:
        raise HTTPException(status_code=503, detail="MCP服务未配置，请联系管理员")
    suffix = extra_path or ""
    if suffix and not suffix.startswith("/"):
        suffix = "/" + suffix
    target = settings.external_mcp_endpoint.rstrip("/") + suffix
    return RedirectResponse(url=target, status_code=307)


# ==================== 综合分析接口 ====================
@app.post("/api/analysis/snapshot",
          operation_id="get_analysis_snapshot",
          summary="获取股票综合分析快照",
          tags=["analysis"])
async def get_analysis_snapshot(request: AnalysisSnapshotRequest) -> Dict[str, Any]:
    """返回单支股票的全量分析快照，用于 MCP/Agent 快速读取"""
    code = request.code
    logger.info(f"[analysis.snapshot] code={code} start")
    start = time.time()

    def _noop(result=None):
        return asyncio.create_task(asyncio.sleep(0, result=result))

    quote_task = asyncio.create_task(_fetch_quote_snapshot(code))
    signals_task = asyncio.create_task(_fetch_news_signals(code, 12)) if request.include_signals else _noop({})
    rec_task = asyncio.create_task(_fetch_recommendations_snapshot(code)) if request.include_recommendations else _noop([])
    holding_task = asyncio.create_task(_fetch_holding_snapshot(code)) if request.include_holding else _noop(None)

    if request.include_history and futu_service:
        history_task = asyncio.create_task(
            futu_service.get_history_kline(
                HistoryKLineRequest(
                    code=code,
                    ktype=request.history_ktype,
                    max_count=request.history_points
                )
            )
        )
    else:
        history_task = _noop()

    if request.include_capital_flow and futu_service:
        flow_task = asyncio.create_task(
            futu_service.get_capital_flow(
                CapitalFlowRequest(code=code, period_type=PeriodType.DAY)
            )
        )
    else:
        flow_task = _noop()

    if request.include_capital_distribution and futu_service:
        distribution_task = asyncio.create_task(
            futu_service.get_capital_distribution(CapitalDistributionRequest(code=code))
        )
    else:
        distribution_task = _noop()

    if request.include_technicals:
        technical_req = TechnicalAnalysisRequest(
            code=code,
            period=request.technical_period,
            indicators=request.technical_indicators
        )
        technical_task = asyncio.create_task(get_technical_indicators(technical_req))
    else:
        technical_task = _noop()

    (quote, signals, recommendations, holding,
     history_resp, flow_resp, distribution_resp, technical_resp) = await asyncio.gather(
        quote_task, signals_task, rec_task, holding_task,
        history_task, flow_task, distribution_task, technical_task
    )

    snapshot: Dict[str, Any] = {
        "code": code,
        "generated_at": datetime.now().isoformat(),
        "quote": quote,
        "session_window": _get_session_window(code)
    }

    if request.include_signals and signals:
        snapshot["signals"] = signals
    if request.include_recommendations and recommendations:
        snapshot["recommendations"] = recommendations
    if request.include_holding and holding:
        snapshot["holding"] = holding
    if request.include_history and isinstance(history_resp, APIResponse) and history_resp.ret_code == 0:
        snapshot["history_kline"] = history_resp.data.get("kline_data")
    if request.include_capital_flow and isinstance(flow_resp, APIResponse) and flow_resp.ret_code == 0:
        snapshot["capital_flow"] = flow_resp.data
    if request.include_capital_distribution and isinstance(distribution_resp, APIResponse) and distribution_resp.ret_code == 0:
        snapshot["capital_distribution"] = distribution_resp.data
    if request.include_technicals and isinstance(technical_resp, dict) and technical_resp.get("ret_code") == 0:
        snapshot["technical_indicators"] = technical_resp.get("data")
        summary = technical_resp.get("data", {}).get("summary") if technical_resp.get("data") else None
        if summary:
            snapshot.setdefault("insights", {})["technical_summary"] = summary

    if signals:
        bullish = len(signals.get("bullish", []))
        bearish = len(signals.get("bearish", []))
        neutral = len(signals.get("neutral", []))
        snapshot.setdefault("insights", {}).update({
            "signal_bullish": bullish,
            "signal_bearish": bearish,
            "signal_neutral": neutral
        })
    if recommendations:
        snapshot.setdefault("insights", {})["recommendation_count"] = len(recommendations)
    if quote:
        snapshot.setdefault("insights", {})["last_price"] = quote.get("price") or quote.get("cur_price")

    cost = time.time() - start
    snapshot["execution_time"] = cost
    logger.info(f"[analysis.snapshot.done] code={code} cost={cost:.3f}s")
    return snapshot


class MultiModelAnalysisRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    models: List[str] = Field(default_factory=lambda: ["deepseek", "kimi"], description="参与分析的模型列表")
    judge_model: str = Field("gemini", description="最终评审模型")
    question: Optional[str] = Field(None, description="额外关注的问题")


class SingleModelAnalysisRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    model: str = Field(..., description="需要调用的模型: deepseek/kimi/gemini")
    question: Optional[str] = Field(None, description="额外问题")


class MultiModelJudgeRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    judge_model: str = Field("gemini", description="评审模型, 例如 gemini/deepseek")
    base_results: List[Dict[str, Any]] = Field(..., description="各模型的原始结果")
    question: Optional[str] = Field(None, description="额外问题")


class FundamentalNewsRefreshRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    size: int = Field(10, ge=10, le=100, description="Metaso 搜索数量")
    days: int = Field(3, ge=1, le=30, description="限定最近N天的资讯，默认3天")


@app.post("/api/analysis/multi_model",
          operation_id="run_multi_model_analysis",
          summary="多模型并行策略分析",
          tags=["analysis"])
async def run_multi_model_analysis(request: MultiModelAnalysisRequest) -> Dict[str, Any]:
    if not _server_ready:
        raise HTTPException(status_code=503, detail="服务器正在初始化中")
    if not multi_model_service:
        raise HTTPException(status_code=503, detail="多模型分析服务不可用")
    snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=request.code))
    context_text = _build_analysis_context_text(snapshot)
    result = await multi_model_service.run_analysis(
        code=request.code,
        models=request.models,
        judge_model=request.judge_model,
        context_text=context_text,
        context_snapshot=snapshot,
        question=request.question,
    )
    return result


@app.post(
    "/api/analysis/multi_model/model",
    operation_id="run_single_model_analysis",
    summary="单模型策略分析",
    tags=["analysis"],
)
async def run_single_model_analysis(request: SingleModelAnalysisRequest) -> Dict[str, Any]:
    if not _server_ready or not multi_model_service:
        raise HTTPException(status_code=503, detail="多模型分析服务不可用")
    snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=request.code))
    context_text = _build_analysis_context_text(snapshot)
    context_snapshot = dict(snapshot)
    context_snapshot["context_text"] = context_text
    result = await multi_model_service.run_single_analysis(
        code=request.code,
        model=request.model,
        context_text=context_text,
        question=request.question,
    )
    return {**result, "context_snapshot": context_snapshot}


@app.post(
    "/api/analysis/multi_model/judge",
    operation_id="run_multi_model_judge",
    summary="多模型评审整合",
    tags=["analysis"],
)
async def run_multi_model_judge(request: MultiModelJudgeRequest) -> Dict[str, Any]:
    if not _server_ready or not multi_model_service:
        raise HTTPException(status_code=503, detail="多模型分析服务不可用")
    snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=request.code))
    context_text = _build_analysis_context_text(snapshot)
    context_snapshot = dict(snapshot)
    context_snapshot["context_text"] = context_text
    judge = await multi_model_service.run_judge_only(
        code=request.code,
        judge_model=request.judge_model,
        context_text=context_text,
        base_results=request.base_results,
        question=request.question,
    )
    judge["context_snapshot"] = context_snapshot
    return judge


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
            "time_contexts": time_contexts,
            
            # 时间区间建议
            "common_periods": {
                "最近1天": {
                    "start": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近3天": {
                    "start": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近1周": {
                    "start": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近1月": {
                    "start": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近3月": {
                    "start": (now - timedelta(days=90)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "年初至今": {
                    "start": now.replace(month=1, day=1).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                }
            },
            
            # LLM提示信息
            "llm_context": {
                "description": "当前服务器时间信息，用于理解用户的模糊时间表达",
                "usage_examples": [
                    "当用户说'最近'时，通常指最近3天",
                    "当用户说'近期'时，通常指最近1周", 
                    "当用户说'这几天'时，通常指最近5天",
                    "股票数据分析建议使用交易日时间范围"
                ]
            }
        }
    }


def _get_next_trading_day(current_time: datetime) -> datetime:
    """计算下一个交易日"""
    next_day = current_time + timedelta(days=1)
    
    # 跳过周末
    while next_day.weekday() >= 5:  # 周六=5, 周日=6
        next_day += timedelta(days=1)
    
    return next_day


async def _persist_dashboard_sessions():
    if not dashboard_session_store:
        return
    snapshot = {}
    async with _dashboard_lock:
        for session_id, info in dashboard_sessions.items():
            snapshot[session_id] = {
                "code": info.get("code"),
                "nickname": info.get("nickname"),
                "created_at": info.get("created_at")
            }
    await asyncio.to_thread(dashboard_session_store.save, snapshot)


def _remove_duplicate_sessions_locked() -> List[Tuple[str, str]]:
    """必须在持有_dashboard_lock时调用，按code去重并返回移除记录(session_id, code)"""
    seen_codes = set()
    duplicates: List[Tuple[str, str]] = []
    for session_id, info in list(dashboard_sessions.items()):
        code = info.get("code")
        if not code:
            continue
        if code in seen_codes:
            duplicates.append((session_id, code))
            dashboard_sessions.pop(session_id, None)
        else:
            seen_codes.add(code)
    return duplicates


def _get_session_window(code: str) -> Dict[str, Any]:
    market = "HK" if code.upper().startswith("HK.") else "US"
    tz_offset = 8 if market == "HK" else -5
    tz = timezone(timedelta(hours=tz_offset))
    today_local = datetime.now(tz).date()

    def local_iso(hour: int, minute: int) -> str:
        dt = datetime.combine(today_local, dtime(hour=hour, minute=minute, tzinfo=tz))
        return dt.astimezone(timezone.utc).isoformat()

    if market == "HK":
        window = {
            "market": "HK",
            "open_time": local_iso(9, 30),
            "break_start": local_iso(12, 0),
            "break_end": local_iso(13, 0),
            "close_time": local_iso(16, 0),
        }
    else:
        window = {
            "market": market,
            "open_time": local_iso(9, 30),
            "close_time": local_iso(16, 0),
        }
    return window


BULLISH_KEYWORDS = ["上涨", "利好", "增持", "创新高", "超预期", "大幅增长", "获批", "回购", "上调"]
BULLISH_KEYWORDS = [...]
BULLISH_KEYWORDS = ["上涨", "利好", "增持", "创新高", "超预期", "大幅增长", "获批", "回购", "上调"]
BEARISH_KEYWORDS = ["下跌", "利空", "警告", "亏损", "裁员", "大幅减少", "下调", "减持", "停牌"]


def _normalize_datetime(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_publish_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 1_000_000_000_000:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            return _normalize_datetime(datetime.fromisoformat(raw))
        except Exception:
            pass
        try:
            dt = parsedate_to_datetime(raw)
            return _normalize_datetime(dt)
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return _normalize_datetime(dt)
            except Exception:
                continue
    return None


def _ensure_dashboard_session(session_id: str) -> Dict[str, Any]:
    session = dashboard_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="dashboard session not found")
    return session


async def _fetch_quote_snapshot(code: str) -> Optional[Dict[str, Any]]:
    if not futu_service:
        logger.warning(f"[quote.snapshot] futu_service_unavailable code={code}")
        return None
    request = StockQuoteRequest(code_list=[code])
    result = await futu_service.get_stock_quote(request)
    if result.ret_code != 0 or not result.data:
        logger.warning(f"[quote.snapshot] ret={result.ret_code} empty={not bool(result.data)} code={code}")
        return None
    quotes = result.data.get("quotes") or []
    if not quotes:
        logger.warning(f"[quote.snapshot] no_quotes code={code}")
        return None
    raw = quotes[0]

    def _to_float(value: Any) -> Optional[float]:
        if value in ("", None):
            return None
        if isinstance(value, (int, float)):
            try:
                as_float = float(value)
                if as_float != as_float:  # NaN
                    return None
                return as_float
            except (TypeError, ValueError):
                return None
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned or cleaned in {"--", "N/A", "null", "-"}:
                return None
            cleaned = cleaned.replace(",", "")
            try:
                if cleaned.endswith("%"):
                    cleaned = cleaned.rstrip("%")
                return float(cleaned)
            except ValueError:
                return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    try:
        last_price = _to_float(raw.get("last_price") or raw.get("price"))
        prev_close = _to_float(raw.get("prev_close_price") or raw.get("prev_close"))
        change_rate = _to_float(raw.get("change_rate"))
        open_price = _to_float(raw.get("open_price") or raw.get("open"))
        high_price = _to_float(raw.get("high_price") or raw.get("high"))
        low_price = _to_float(raw.get("low_price") or raw.get("low"))
        volume = _to_float(raw.get("volume"))
        turnover = _to_float(raw.get("turnover"))
        change_value = None
        if last_price is not None and prev_close is not None:
            change_value = last_price - prev_close
            if (change_rate is None or change_rate == 0) and prev_close:
                try:
                    change_rate = (change_value / prev_close) * 100
                except ZeroDivisionError:
                    change_rate = None
        return {
            "code": raw.get("code"),
            "name": raw.get("stock_name") or raw.get("name"),
            "price": last_price,
            "last_price": last_price,
            "change_rate": change_rate,
            "change_value": change_value,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "prev_close": prev_close,
            "volume": volume,
            "turnover": turnover,
            "update_time": raw.get("update_time")
        }
    except Exception:
        return raw


async def _fetch_recommendations_snapshot(code: str) -> List[Dict[str, Any]]:
    if not recommendation_storage:
        return []
    req = RecommendationQueryRequest(code=code, limit=5)
    return await asyncio.to_thread(recommendation_storage.get_recommendations, req.dict())


async def _fetch_holding_snapshot(code: str) -> Optional[Dict[str, Any]]:
    if not futu_service or not futu_service.has_trade_connection():
        return None
    try:
        request = PositionListRequest(code=code, trd_env=TrdEnv.REAL)
        result = await futu_service.get_position_list(request)
        if result.ret_code != 0 or not result.data:
            return None
        positions = result.data.get("position_list") or []
        if not positions:
            return None
        pos = positions[0]
        qty = float(pos.get("qty") or 0)
        cost_price = float(pos.get("cost_price") or 0)
        last_price = pos.get("price") or pos.get("last_price")
        if last_price in (None, "", 0) and futu_service:
            quote = await _fetch_quote_snapshot(code)
            if quote and quote.get("price") is not None:
                last_price = quote["price"]
        last_price = float(last_price or 0)
        pl_val = float(pos.get("pl_val") or 0)
        pl_ratio = float(pos.get("pl_ratio") or 0)  # already percent
        return {
            "持仓": qty,
            "成本": cost_price,
            "现价": last_price,
            "盈亏": pl_val,
            "盈亏比例": pl_ratio,
        }
    except Exception as exc:
        logger.debug(f"获取持仓失败: {exc}")
        return None


async def _fetch_news_signals(code: str, size: int = 12, refresh: bool = True, days: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    signals = {"bullish": [], "bearish": [], "neutral": [], "sector_news": [], "macro_news": []}
    run_remote = refresh and fundamental_service.is_configured()
    days = max(1, min(int(days or 3), 30))
    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=days)
    max_dt = now_utc + timedelta(days=1)  # 防止未来日期污染

    def _normalize_publish_time(value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1e12:
                ts = ts / 1000.0
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                return None
        text = str(value).strip()
        if not text:
            return None
        lower = text.lower()
        # 相对时间处理
        if lower in {"刚刚", "刚才", "just now", "now"}:
            return now_utc.isoformat()
        rel_match = re.match(r"(\d+)\s*(分钟|分|小时|天|日)\s*前?$", text)
        if rel_match:
            amount = int(rel_match.group(1))
            unit = rel_match.group(2)
            delta_kwargs = {}
            if unit in {"分钟", "分"}:
                delta_kwargs["minutes"] = amount
            elif unit in {"小时"}:
                delta_kwargs["hours"] = amount
            elif unit in {"天", "日"}:
                delta_kwargs["days"] = amount
            if delta_kwargs:
                return (now_utc - timedelta(**delta_kwargs)).isoformat()
        if lower in {"昨天", "yesterday"}:
            return (now_utc - timedelta(days=1)).isoformat()
        # 直接解析时间戳/日期
        try:
            parsed = parsedate_to_datetime(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d"):
            try:
                dt = datetime.strptime(text, fmt)
                if fmt in ("%m-%d", "%m/%d"):
                    dt = dt.replace(year=now_utc.year)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                continue
        # 手工提取数字日期
        digits = re.findall(r"\d+", text)
        if len(digits) >= 3:
            year, month, day = digits[0], digits[1], digits[2]
            hour = digits[3] if len(digits) > 3 else "0"
            minute = digits[4] if len(digits) > 4 else "0"
            second = digits[5] if len(digits) > 5 else "0"
            try:
                dt = datetime(
                    int(year),
                    int(month),
                    int(day),
                    int(hour),
                    int(minute),
                    int(second),
                    tzinfo=timezone.utc
                )
                return dt.isoformat()
            except Exception:
                pass
        return None


    async def _build_search_query() -> str:
        def _ensure_recent(q: str) -> str:
            text = q.lower()
            recency_token = f"最近{days}天"
            recent_tokens = [
                "最近", "本周", "过去", "近一周", "last 7 days", "past week", "today", "yesterday", "last week",
                recency_token.lower(), f"近{days}天", f"{days}天"
            ]
            if any(tok.lower() in text for tok in recent_tokens):
                return q
            return f"{q} {recency_token}"

        default_query = _ensure_recent(f"{code} 最新 股票新闻 基本面")
        if not run_remote or not deepseek_service or not deepseek_service.is_configured():
            return default_query
        company_name = code
        try:
            quote_info = await _fetch_quote_snapshot(code)
            if quote_info and quote_info.get("name"):
                company_name = str(quote_info["name"])
        except Exception:
            company_name = code
        prompt = (
            "你是金融情报检索专家。请基于股票代码和公司名称，提供一个用于新闻搜索的简短中文关键词，"
            "聚焦基本面、财报、政策或竞争情报，不超过18个汉字。"
            '输出 JSON，如 {"query": "美团 基本面 财报"}。'
            f"\n股票代码: {code}\n公司名称: {company_name}"
        )
        try:
            raw = await deepseek_service.chat("你是资讯检索专家。", prompt, temperature=0.2)
            if raw:
                text = raw.strip().strip('`')
                if text.lower().startswith("json"):
                    text = text[4:].lstrip()
                data = json.loads(text)
                if isinstance(data, dict):
                    query = data.get("query")
                    if isinstance(query, str) and query.strip():
                        return _ensure_recent(query.strip())
        except Exception as exc:
            logger.debug(f"生成检索关键词失败: {exc}")
        return default_query

    def _build_code_tokens(symbol: str) -> List[str]:
        base = symbol.upper()
        tokens = {base}
        if "." in base:
            market, num = base.split(".", 1)
            tokens.update({num, num.lstrip("0") or num, f"{market}{num}", f"{market}{num.lstrip('0') or num}", f"{num}.{market}", f"{num.lstrip('0') or num}.{market}"})
        tokens.update({base.replace(".", ""), base.replace(".", " ")})
        return [token for token in tokens if token]

    code_tokens = _build_code_tokens(code)
    search_query = await _build_search_query()

    def _has_code_token(record: Dict[str, Any]) -> bool:
        title = (record.get("title") or "").upper()
        snippet = (record.get("snippet") or "").upper()
        merged = f"{title} {snippet}"
        return any(token and token in merged for token in code_tokens)

    def _classify_scope(record: Dict[str, Any], analysis: Optional[Dict[str, Any]]) -> str:
        # 优先：如果当前请求的 code 与记录的 code 一致，直接视为 direct，防止被误判为 sector/macro
        if record.get("code") and record.get("code") == code:
            return "direct"
        if analysis:
            scope = analysis.get("related_scope")
            if isinstance(scope, str):
                scope_lower = scope.lower()
                if scope_lower in {"direct", "sector", "macro"}:
                    if scope_lower == "direct" and not _has_code_token(record):
                        return "sector"
                    return scope_lower
            related_val = analysis.get("related")
            if isinstance(related_val, bool):
                if related_val and _has_code_token(record):
                    return "direct"
                if related_val:
                    return "sector"
                return "macro"
        if _has_code_token(record):
            return "direct"
        return "macro"

    def _fallback_analysis(text: str) -> Dict[str, Any]:
        lowered = text.lower()
        sentiment = "neutral"
        if any(key.lower() in lowered for key in BEARISH_KEYWORDS):
            sentiment = "bearish"
        elif any(key.lower() in lowered for key in BULLISH_KEYWORDS):
            sentiment = "bullish"
        scope = "direct" if any(token.lower() in lowered for token in code_tokens) else "macro"
        return {
            "sentiment": sentiment,
            "confidence": 0.4,
            "impact_horizon": "短期",
            "volatility_bias": "中性",
            "themes": [],
            "risk_factors": [],
            "opportunity_factors": [],
            "summary": text[:100],
            "action_hint": "",
            "related": scope == "direct",
            "related_scope": scope,
            "analysis_provider": "fallback"
        }

    async def _ensure_analysis(item: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "code": code,
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "source": item.get("source"),
            "publish_time": item.get("publish_time"),
            "url": item.get("url")
        }
        text = f"{payload['title'] or ''} {payload['snippet'] or ''}"
        analysis: Optional[Dict[str, Any]] = None
        if deepseek_service and deepseek_service.is_configured():
            try:
                analysis = await deepseek_service.analyze_fundamental_news(payload)
                if analysis is not None:
                    analysis["analysis_provider"] = "deepseek"
            except Exception as exc:
                logger.warning(
                    f"[fundamental.analysis] DeepSeek 调用失败，使用兜底分析 code={code} title={payload['title']} err={exc}"
                )
        if not analysis:
            detail = None
            if deepseek_service:
                detail = getattr(deepseek_service, "last_error_message", None)
            logger.warning(
                "[fundamental.analysis] 使用关键词兜底情绪，DeepSeek 无响应或解析失败 code=%s title=%s detail=%s",
                code,
                payload["title"],
                detail or "无",
            )
            analysis = _fallback_analysis(text)
            analysis["analysis_provider"] = "fallback"
        return analysis

    async def _repair_existing_records(quota: int = 5):
        if not fundamental_storage or not deepseek_service or not deepseek_service.is_configured():
            return
        pending_items = fundamental_storage.get_reanalysis_queue(code, limit=quota)
        if not pending_items:
            return
        logger.info(f"[fundamental.repair] code={code} pending={len(pending_items)} 触发重算")
        for pending in pending_items:
            try:
                analysis = await _ensure_analysis(pending)
                pending["analysis"] = analysis
                fundamental_storage.upsert(pending)
            except Exception as exc:
                logger.warning(f"[fundamental.repair] 重算失败 code={code} title={pending.get('title')} err={exc}")

    try:
        request = FundamentalSearchRequest(
            q=search_query,
            scope="news",
            includeSummary=True,
            size=min(max(size, 10), 100),
            includeRawContent=False,
            conciseSnippet=True
        )
        response = await fundamental_service.search_fundamental_info(request)
        results = response.results or []
        fetched_count = len(results)
        kept_count = 0
        new_count = 0
        updated_count = 0
        skipped_no_time = 0
        skipped_cutoff = 0
        max_items = min(len(results), size)
        for item in results[:max_items]:
            raw_publish_time = item.publish_time
            normalized_publish_time = _normalize_publish_time(raw_publish_time)
            if cutoff_dt:
                if not normalized_publish_time:
                    # 缺失或无法解析发布时间，跳过，避免时间轴被旧数据污染
                    skipped_no_time += 1
                    continue
                try:
                    dt = datetime.fromisoformat(normalized_publish_time.replace("Z", "+00:00"))
                    if dt < cutoff_dt or dt > max_dt:
                        skipped_cutoff += 1
                        continue
                except Exception:
                    skipped_no_time += 1
                    continue
            record = {
                "code": code,
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "snippet": item.snippet,
                "raw_publish_time": raw_publish_time,
                "publish_time": normalized_publish_time or raw_publish_time or now_utc.isoformat(),
            }
            unique_key = None
            stored = None
            if fundamental_storage:
                unique_key = fundamental_storage.make_unique_key(
                    code,
                    item.title or "",
                    item.url or "",
                    normalized_publish_time or raw_publish_time
                )
                stored = fundamental_storage.get_by_unique_key(unique_key)
            analysis = stored.get("analysis") if stored and stored.get("analysis") else None
            if not analysis:
                analysis = await _ensure_analysis(record)
            scope = _classify_scope(record, analysis)
            if scope != "direct":
                logger.info(
                    f"[fundamental.filter] 识别为{scope}级资讯 code={code} title={record.get('title')}"
                )
            record["analysis"] = analysis
            if fundamental_storage:
                record["unique_key"] = unique_key
                existed = bool(stored)
                fundamental_storage.upsert(record)
                if existed:
                    updated_count += 1
                else:
                    new_count += 1
            kept_count += 1
        logger.info(
            f"[fundamental.refresh] code={code} fetched={fetched_count} kept={kept_count} "
            f"new={new_count} updated={updated_count} "
            f"skip_no_time={skipped_no_time} skip_cutoff={skipped_cutoff} days={days}"
        )
    except Exception as exc:
        logger.debug(f"基本面增量搜索失败: {exc}")

    if run_remote:
        refresh_quota = max(3, min(10, max(size // 2, 1)))
        await _repair_existing_records(quota=refresh_quota)

    def _build_cached_news_signals() -> Dict[str, List[Dict[str, Any]]]:
        local_signals = {key: [] for key in signals.keys()}
        stored_records: List[Dict[str, Any]] = []
        sector_records: List[Dict[str, Any]] = []
        macro_records: List[Dict[str, Any]] = []
        preview_times: List[str] = []

        def _sort_key_by_time(rec: Dict[str, Any]):
            pt = rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen") or ""
            norm = _normalize_publish_time(pt) if pt else None
            try:
                return datetime.fromisoformat((norm or "").replace("Z", "+00:00"))
            except Exception:
                return datetime.min

        if fundamental_storage:
            raw_records = fundamental_storage.get_recent_news(code, limit=40)
            # 按发布时间降序排序，避免字符串排序导致新数据被埋
            raw_records_sorted = sorted(raw_records, key=_sort_key_by_time, reverse=True)
            for rec in raw_records_sorted:
                if rec.get("code") and rec.get("code") != code:
                    continue
                scope = _classify_scope(rec, rec.get("analysis"))
                if scope == "direct":
                    stored_records.append(rec)
                elif scope == "sector":
                    sector_records.append(rec)
                else:
                    macro_records.append(rec)
        if not stored_records:
            logger.info(f"[fundamental.signals.cache] code={code} 本地无direct资讯，sector={len(sector_records)} macro={len(macro_records)}")
            local_signals["daily_metrics"] = []
            return local_signals
        logger.info(
            f"[fundamental.signals.cache.raw] code={code} direct={len(stored_records)} sector={len(sector_records)} macro={len(macro_records)}"
        )
        daily_buckets: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: {
                "counts": {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0},
                "weights": {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}
            }
        )
        for rec in stored_records:
            analysis = rec.get("analysis") or {}
            raw_sentiment = analysis.get("sentiment") or "neutral"
            sentiment = "neutral"
            if raw_sentiment in ("bullish", "利好", "看涨"):
                sentiment = "bullish"
            elif raw_sentiment in ("bearish", "利空", "看跌"):
                sentiment = "bearish"
            publish_time_val = rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen")
            normalized_publish_time = _normalize_publish_time(publish_time_val) if publish_time_val else None
            if normalized_publish_time and len(preview_times) < 3:
                preview_times.append(normalized_publish_time)
            entry = {
                "title": rec.get("title"),
                "snippet": rec.get("snippet"),
                "source": rec.get("source"),
                "url": rec.get("url"),
                "publish_time": normalized_publish_time or publish_time_val,
                "published_at": normalized_publish_time or publish_time_val,
                "analysis": analysis
            }
            local_signals.setdefault(sentiment, []).append(entry)
            publish_date = (normalized_publish_time or publish_time_val or "")[:10]
            if publish_date:
                bucket = daily_buckets[publish_date]
                bucket["counts"][sentiment] += 1
                impact_score = float(analysis.get("impact_score") or 50)
                novelty_score = float(analysis.get("novelty_score") or analysis.get("magnitude_score") or 50)
                weight = max(0.1, min((impact_score * 0.7 + novelty_score * 0.3) / 100, 2.0))
                if analysis.get("effectiveness") == "stale":
                    weight *= 0.3
                elif analysis.get("effectiveness") == "diminished":
                    weight *= 0.6
                bucket["weights"][sentiment] += weight
        daily_metrics = []
        for date, bucket in sorted(daily_buckets.items(), key=lambda x: x[0], reverse=True):
            counts = bucket["counts"]
            weights = bucket["weights"]
            total = counts["bullish"] + counts["bearish"] + counts["neutral"]
            total_weight = weights["bullish"] + weights["bearish"] + weights["neutral"]
            if total == 0:
                continue
            weight_score = (weights["bullish"] - weights["bearish"]) / total_weight if total_weight else 0.0
            score = (counts["bullish"] - counts["bearish"]) / total
            daily_metrics.append({
                "date": date,
                "bullish": counts["bullish"],
                "bearish": counts["bearish"],
                "neutral": counts["neutral"],
                "score": round(score, 2),
                "weighted_score": round(weight_score, 2)
            })
        local_signals["daily_metrics"] = daily_metrics
        local_signals["sector_news"] = [
            {
                "title": rec.get("title"),
                "snippet": rec.get("snippet"),
                "source": rec.get("source"),
                "url": rec.get("url"),
                "publish_time": _normalize_publish_time(rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen")) or rec.get("publish_time"),
                "analysis": rec.get("analysis"),
            }
            for rec in sector_records
        ]
        local_signals["macro_news"] = [
            {
                "title": rec.get("title"),
                "snippet": rec.get("snippet"),
                "source": rec.get("source"),
                "url": rec.get("url"),
                "publish_time": _normalize_publish_time(rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen")) or rec.get("publish_time"),
                "analysis": rec.get("analysis"),
            }
            for rec in macro_records
        ]
        logger.info(
            f"[fundamental.signals.cache] code={code} bullish={len(local_signals.get('bullish', []))} "
            f"bearish={len(local_signals.get('bearish', []))} total_direct={len(stored_records)} "
            f"sector={len(sector_records)} macro={len(macro_records)} "
            f"top_publish_time={preview_times}"
        )
        return local_signals

    return _build_cached_news_signals()

def _normalize_kline_cache_scope(request: HistoryKLineRequest) -> Tuple[str, str, str]:
    """生成用于缓存的K线范围标识，避免不同请求互相污染"""
    ktype_value = request.ktype.value if hasattr(request.ktype, "value") else str(request.ktype)
    autype_value = request.autype.value if hasattr(request.autype, "value") else str(request.autype)
    start_token = request.start or f"recent:{request.max_count}"
    end_token = request.end or "latest"
    return f"{ktype_value}:{autype_value}", start_token, end_token


# ==================== 原有行情接口（增强版） ====================
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
    ktype_token, cache_start, cache_end = _normalize_kline_cache_scope(request)
    
    try:
        # 1. 尝试从缓存获取数据
        if cache_manager:
            cached_data = await cache_manager.get_kline_data(
                request.code, ktype_token, cache_start, cache_end
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
                request.code, ktype_token,
                cache_start, cache_end,
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


# ==================== 技术分析接口 ====================
@app.post("/api/analysis/technical_indicators",
          operation_id="get_technical_indicators",
          summary="获取技术分析指标",
          description="计算MACD、RSI、布林带等技术指标，支持缓存优化")
async def get_technical_indicators(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """获取技术分析指标"""
    start_time = time.time()
    cache_hit = False
    
    logger.info(f"🔍 开始处理技术分析请求: {request.code}, 指标: {request.indicators}")
    
    try:
        # 1. 检查指标缓存
        if cache_manager:
            cached_indicators = await cache_manager.get_indicator_data(
                "comprehensive", request.code, request.dict()
            )
            if cached_indicators:
                cache_hit = True
                execution_time = time.time() - start_time
                
                return {
                    "ret_code": 0,
                    "ret_msg": "技术分析获取成功（缓存）",
                    "data": cached_indicators,
                    "execution_time": execution_time,
                    "cache_hit": True,
                    "data_source": "cache",
                    "timestamp": datetime.now().isoformat()
                }
        
        # 2. 获取K线数据（优先从缓存）
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 根据K线类型智能计算需要的数据量和时间范围
        ktype_multipliers = {
            "K_1M": 1440,     # 1分钟: 1天=1440根K线
            "K_5M": 288,      # 5分钟: 1天=288根K线  
            "K_15M": 96,      # 15分钟: 1天=96根K线
            "K_30M": 48,      # 30分钟: 1天=48根K线
            "K_60M": 24,      # 60分钟: 1天=24根K线
            "K_DAY": 1,       # 日线: 1天=1根K线
            "K_WEEK": 0.2,    # 周线: 1天=0.2根K线
            "K_MON": 0.05     # 月线: 1天=0.05根K线
        }
        
        ktype_str = request.ktype.value if hasattr(request.ktype, 'value') else str(request.ktype)
        multiplier = ktype_multipliers.get(ktype_str, 1)
        
        # 计算需要的最小数据量（考虑技术指标计算需求）
        min_required_points = max(
            request.macd_slow + 10,  # MACD需要慢线周期+额外缓冲
            request.rsi_period + 10,  # RSI需要周期+缓冲
            request.bollinger_period + 10,  # 布林带需要周期+缓冲
            50  # 最少50个数据点
        )
        
        # 根据K线频率计算需要的天数
        if multiplier > 1:  # 分钟线
            days_needed = max(
                int(min_required_points / multiplier) + 15,  # 基于数据点计算+更大缓冲
                30  # 至少30天，对于30分钟线确保足够数据
            )
        else:  # 日线、周线、月线
            days_needed = max(
                int(min_required_points / multiplier) + 20,
                90  # 至少90天
            )
        
        start_date = (datetime.now() - timedelta(days=days_needed)).strftime('%Y-%m-%d')
        max_count = min(1000, int(min_required_points * 2))  # 增加到2倍缓冲并提高上限
        
        logger.info(f"📊 准备获取K线数据: {request.code}, {start_date} ~ {end_date}")
        logger.info(f"📊 K线类型: {ktype_str}, 预计需要: {min_required_points}个数据点, 查询天数: {days_needed}, max_count: {max_count}")
        
        kline_request = HistoryKLineRequest(
            code=request.code,
            start=start_date,
            end=end_date,
            ktype=request.ktype,
            max_count=max_count,
            optimization=request.optimization
        )
        
        logger.info(f"📞 调用K线API...")
        kline_result = await get_history_kline_enhanced(kline_request)
        logger.info(f"📈 K线API返回: {kline_result.ret_code}, {kline_result.ret_msg}")
        
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
        
        # 3. 计算技术指标
        logger.info(f"⚙️  开始计算技术指标，K线数据量: {len(kline_data)}")
        
        config = IndicatorConfig(
            macd_fast=request.macd_fast,
            macd_slow=request.macd_slow,
            macd_signal=request.macd_signal,
            rsi_period=request.rsi_period,
            rsi_overbought=request.rsi_overbought,
            rsi_oversold=request.rsi_oversold,
            bollinger_period=request.bollinger_period,
            bollinger_std=request.bollinger_std,
            ma_periods=request.ma_periods
        )
        
        logger.info("🧮 创建技术分析对象...")
        technical_data = TechnicalIndicators.from_kline_data(kline_data, config)
        logger.info("📈 计算所有指标...")
        indicators = technical_data.calculate_all_indicators()
        logger.info(f"✅ 指标计算完成，包含: {list(indicators.keys())}")
        
        # 4. 构建简化且LLM友好的响应数据
        logger.info("📋 构建简化响应数据...")
        
        # 提取关键指标的当前值和信号，避免过长的历史数据
        simplified_data = _create_simplified_response(indicators, request.code, len(kline_data))
        
        logger.info(f"🔍 简化后数据结构: {list(simplified_data.keys()) if isinstance(simplified_data, dict) else type(simplified_data)}")
        
        response_data = {
            "code": request.code,
            "period": request.period,
            "data_points": len(kline_data),
            "indicators": simplified_data,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("✅ 响应数据构建完成")
        
        # 5. 存储指标到缓存
        if cache_manager:
            await cache_manager.store_indicator_data(
                "comprehensive", request.code, request.model_dump(), response_data
            )
        
        execution_time = time.time() - start_time
        
        # 使用通用的字典响应格式，避免严格的模型验证
        return {
            "ret_code": 0,
            "ret_msg": "技术分析计算完成",
            "data": response_data,
            "execution_time": execution_time,
            "cache_hit": cache_hit,
            "data_source": "calculated",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"技术分析计算失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"技术分析异常: {e}",
            "data": None
        }


def _create_simplified_response(indicators: Dict[str, Any], code: str, data_points: int) -> Dict[str, Any]:
    """创建简化的LLM友好响应格式
    
    只保留关键信息：
    - 当前值 (current)
    - 信号 (signal) 
    - 简要描述
    避免过长的历史数据序列
    """
    
    def extract_current_value(indicator_data):
        """提取指标的当前值"""
        if not isinstance(indicator_data, dict):
            # logger.debug(f"🔍 指标数据不是字典: {type(indicator_data)}")
            return None
            
        current = indicator_data.get("current")
        # logger.debug(f"🔍 当前值原始数据: {current} (类型: {type(current)})")
        
        if isinstance(current, dict):
            # 过滤有效的数值
            valid_current = {k: v for k, v in current.items() 
                           if v is not None and isinstance(v, (int, float)) and not (isinstance(v, float) and (v != v or abs(v) == float('inf')))}
            # logger.debug(f"🔍 过滤后的当前值: {valid_current}")
            return valid_current if valid_current else None
        elif isinstance(current, (int, float)) and not (isinstance(current, float) and (current != current or abs(current) == float('inf'))):
            return current
        return None
    
    def extract_signal(indicator_data):
        """提取指标信号"""
        if isinstance(indicator_data, dict):
            signal = indicator_data.get("signal")
            # logger.debug(f"🔍 信号数据: {signal}")
            return signal
        return None
    
    simplified = {}
    
    # 处理趋势指标 (MACD, MA, EMA等)
    if "trend_indicators" in indicators and indicators["trend_indicators"]:
        # logger.info("🔍 处理趋势指标...")
        trend_data = {}
        trend_indicators = indicators["trend_indicators"]
        
        # MACD
        if "macd" in trend_indicators:
            # logger.info("🔍 处理MACD...")
            macd = trend_indicators["macd"]
            # logger.debug(f"🔍 MACD原始数据: {macd}")
            current_macd = extract_current_value(macd)
            if current_macd:
                trend_data["macd"] = {
                    "current": current_macd,
                    "signal": extract_signal(macd) or "中性",
                    "description": "MACD动量指标"
                }
                # logger.info(f"🔍 MACD处理成功: {trend_data['macd']}")
            # else:
                # logger.warning("🔍 MACD当前值为空")
        
        # 移动平均线
        if "moving_averages" in trend_indicators:
            # logger.info("🔍 处理移动平均线...")
            ma = trend_indicators["moving_averages"]
            # logger.debug(f"🔍 MA原始数据: {ma}")
            current_ma = extract_current_value(ma)
            if current_ma:
                trend_data["moving_averages"] = {
                    "current": current_ma,
                    "signal": extract_signal(ma) or "中性",
                    "description": "移动平均线"
                }
                # logger.info(f"🔍 MA处理成功: {trend_data['moving_averages']}")
            # else:
                # logger.warning("🔍 MA当前值为空")
        
        if trend_data:
            simplified["trend_indicators"] = trend_data
            # logger.info(f"🔍 趋势指标处理完成: {list(trend_data.keys())}")
    
    # 处理动量指标 (RSI, KDJ等)
    if "momentum_indicators" in indicators and indicators["momentum_indicators"]:
        # logger.info("🔍 处理动量指标...")
        momentum_data = {}
        momentum_indicators = indicators["momentum_indicators"]
        
        # RSI
        if "rsi" in momentum_indicators:
            # logger.info("🔍 处理RSI...")
            rsi = momentum_indicators["rsi"]
            # logger.debug(f"🔍 RSI原始数据: {rsi}")
            current_rsi = extract_current_value(rsi)
            if current_rsi:
                momentum_data["rsi"] = {
                    "current": current_rsi,
                    "signal": extract_signal(rsi) or "中性",
                    "description": "相对强弱指标"
                }
                # logger.info(f"🔍 RSI处理成功: {momentum_data['rsi']}")
            # else:
                # logger.warning("🔍 RSI当前值为空")
        
        if momentum_data:
            simplified["momentum_indicators"] = momentum_data
            # logger.info(f"🔍 动量指标处理完成: {list(momentum_data.keys())}")
    
    # 处理技术分析总结
    if "summary" in indicators and indicators["summary"]:
        # logger.info("🔍 处理技术分析总结...")
        summary = indicators["summary"]
        # logger.debug(f"🔍 Summary原始数据: {summary}")
        if isinstance(summary, dict):
            clean_summary = {k: v for k, v in summary.items() if v is not None and v != ""}
            if clean_summary:
                simplified["summary"] = clean_summary
                # logger.info(f"🔍 Summary处理成功: {clean_summary}")
    
    # 如果所有指标都无效，返回基本信息
    if not simplified:
        logger.warning("🔍 所有指标都无效，返回基本信息")
        simplified = {
            "status": "数据计算中，部分指标可能需要更多历史数据",
            "data_points": data_points,
            "note": "技术指标需要足够的历史数据才能计算准确"
        }
    
    logger.info(f"✅ 简化数据包含: {list(simplified.keys())}")
    return simplified


def _clean_indicator_data(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """清理指标数据中的None值，确保Pydantic验证通过"""
    
    def clean_dict_values(data: Dict[str, Any]) -> Dict[str, Any]:
        """递归清理字典中的None值"""
        if not isinstance(data, dict):
            return data
            
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, dict):
                # 递归清理嵌套字典
                cleaned_value = clean_dict_values(value)
                # 只保留包含有效数据的字典
                if cleaned_value:
                    cleaned[key] = cleaned_value
            elif isinstance(value, list):
                # 清理列表，移除None值
                cleaned_list = [v for v in value if v is not None]
                if cleaned_list:
                    cleaned[key] = cleaned_list
            elif value is not None:
                # 保留非None值
                cleaned[key] = value
            # 跳过None值
                
        return cleaned
    
    def clean_indicator_structure(category_data: Dict[str, Any]) -> Dict[str, Any]:
        """清理指标类别数据结构"""
        if not isinstance(category_data, dict):
            return category_data
            
        cleaned_category = {}
        
        for indicator_name, indicator_data in category_data.items():
            if not isinstance(indicator_data, dict):
                # 如果不是字典，直接保留（如signal字符串）
                cleaned_category[indicator_name] = indicator_data
                continue
                
            cleaned_indicator = {}
            
            # 处理values字段
            if "values" in indicator_data:
                values = indicator_data["values"]
                if isinstance(values, dict):
                    cleaned_values = clean_dict_values(values)
                    if cleaned_values:
                        cleaned_indicator["values"] = cleaned_values
                elif isinstance(values, list):
                    cleaned_values = [v for v in values if v is not None]
                    if cleaned_values:
                        cleaned_indicator["values"] = cleaned_values
                elif values is not None:
                    cleaned_indicator["values"] = values
            
            # 处理current字段 - 这是关键字段
            if "current" in indicator_data:
                current = indicator_data["current"]
                if isinstance(current, dict):
                    # 过滤掉None值，只保留有效的float值
                    cleaned_current = {k: v for k, v in current.items() if v is not None and isinstance(v, (int, float))}
                    if cleaned_current:
                        cleaned_indicator["current"] = cleaned_current
                elif current is not None and isinstance(current, (int, float)):
                    cleaned_indicator["current"] = current
                # 如果current全是None或无效，则设为None，这样Pydantic会接受Optional类型
                if "current" not in cleaned_indicator:
                    cleaned_indicator["current"] = None
            
            # 处理其他字段
            for field, value in indicator_data.items():
                if field not in ["values", "current"]:
                    if value is not None:
                        cleaned_indicator[field] = value
            
            # 只有当清理后的指标数据非空时才保留
            if cleaned_indicator:
                cleaned_category[indicator_name] = cleaned_indicator
        
        return cleaned_category
    
    # 清理所有类别的指标数据
    cleaned_indicators = {}
    
    for category, category_data in indicators.items():
        if category == "summary":
            # summary是简单的字符串字典，直接保留
            if isinstance(category_data, dict):
                cleaned_summary = {k: v for k, v in category_data.items() if v is not None}
                if cleaned_summary:
                    cleaned_indicators[category] = cleaned_summary
        else:
            # 清理技术指标数据
            cleaned_category = clean_indicator_structure(category_data)
            if cleaned_category:
                cleaned_indicators[category] = cleaned_category
    
    return cleaned_indicators


@app.post("/api/analysis/macd",
          operation_id="get_macd_indicator",
          summary="获取MACD指标")
async def get_macd_indicator(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """单独获取MACD指标"""
    # 复用comprehensive接口但只返回MACD
    request.indicators = [IndicatorType.MACD]
    return await get_technical_indicators(request)


@app.post("/api/analysis/rsi",
          operation_id="get_rsi_indicator", 
          summary="获取RSI指标")
async def get_rsi_indicator(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """单独获取RSI指标"""
    request.indicators = [IndicatorType.RSI]
    return await get_technical_indicators(request)


# ==================== 缓存管理接口 ====================
@app.post("/api/system/request_quote_rights",
          operation_id="request_quote_rights", 
          summary="🔧 请求最高行情权限",
          description="手动请求最高行情权限，解决权限被抢占的问题")
async def request_quote_rights() -> Dict[str, Any]:
    """手动请求最高行情权限"""
    if not _server_ready or not futu_service:
        return {
            "success": False,
            "message": "服务未就绪",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # 强制检查并请求权限
        logger.info("📞 接收到手动权限请求...")
        success = await futu_service._check_and_ensure_quote_rights(force_check=True)
        
        return {
            "success": success,
            "message": "权限请求成功" if success else "权限请求失败，请检查OpenD连接和Telnet端口",
            "rights_checked": futu_service._quote_rights_checked,
            "last_check_time": futu_service._last_quote_rights_check,
            "auto_request_enabled": futu_service._quote_rights_auto_request,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"手动权限请求异常: {str(e)}")
        return {
            "success": False,
            "message": f"权限请求异常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/cache/status",
         operation_id="get_cache_status",
         summary="获取缓存状态")
async def get_cache_status(detailed: bool = False) -> Dict[str, Any]:
    """获取缓存状态"""
    try:
        if not cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        stats = await cache_manager.get_cache_stats()
        
        # 计算使用率
        memory_usage_ratio = stats.get("memory_cache_size", 0) / max(stats.get("memory_max_size", 1), 1)
        
        # 健康状态评估
        health_status = "healthy"
        recommendations = []
        
        if memory_usage_ratio > 0.9:
            health_status = "warning"
            recommendations.append("内存缓存使用率过高，建议清理")
        
        if not stats.get("redis_available", False):
            health_status = "degraded"
            recommendations.append("Redis不可用，建议检查连接")
        
        cache_stats = CacheStats(
            memory_cache_size=stats.get("memory_cache_size", 0),
            memory_max_size=stats.get("memory_max_size", 0),
            memory_usage_ratio=memory_usage_ratio,
            redis_available=stats.get("redis_available", False),
            redis_connected=stats.get("redis_connected"),
            redis_memory_usage=stats.get("redis_memory_usage"),
            sqlite_available=stats.get("sqlite_available", False),
            sqlite_kline_count=stats.get("sqlite_kline_count"),
            sqlite_indicator_count=stats.get("sqlite_indicator_count")
        )
        
        response_data = CacheStatusResponse(
            stats=cache_stats,
            detailed_info=stats if detailed else None,
            health_status=health_status,
            recommendations=recommendations
        )
        
        return {
            "ret_code": 0,
            "ret_msg": "缓存状态获取成功",
            "data": response_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"获取缓存状态失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"获取缓存状态异常: {e}",
            "data": None
        }


@app.post("/api/cache/preload",
          operation_id="preload_cache_data",
          summary="预加载缓存数据")
async def preload_cache_data(request: CachePreloadRequest) -> Dict[str, Any]:
    """预加载缓存数据"""
    start_time = time.time()
    
    try:
        if not cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        # 执行预加载
        await cache_manager.preload_data(request.symbols, request.days)
        
        execution_time = time.time() - start_time
        
        response_data = CacheOperationResponse(
            success=True,
            message=f"成功预加载 {len(request.symbols)} 只股票 {request.days} 天的数据",
            affected_items=len(request.symbols),
            execution_time=execution_time
        )
        
        return {
            "ret_code": 0,
            "ret_msg": "缓存预加载完成",
            "data": response_data,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"缓存预加载失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"缓存预加载异常: {e}",
            "data": None
        }


@app.delete("/api/cache/clear",
           operation_id="clear_cache_data",
           summary="清理缓存数据")
async def clear_cache_data(request: CacheClearRequest) -> Dict[str, Any]:
    """清理缓存数据"""
    start_time = time.time()
    
    try:
        if not cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        # 执行清理
        await cache_manager.clear_cache(request.cache_type.value)
        
        execution_time = time.time() - start_time
        
        response_data = CacheOperationResponse(
            success=True,
            message=f"成功清理 {request.cache_type.value} 缓存",
            execution_time=execution_time
        )
        
        return {
            "ret_code": 0,
            "ret_msg": "缓存清理完成",
            "data": response_data,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"缓存清理失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"缓存清理异常: {e}",
            "data": None
        }


# ==================== 原有接口保持兼容 ====================
@app.post("/api/quote/stock_basicinfo",
          operation_id="get_stock_basicinfo",
          summary="获取股票基本信息",
          description="获取指定市场和证券类型的股票基本信息列表")
async def get_stock_basicinfo(request: StockBasicInfoRequest) -> APIResponse:
    """获取股票基本信息"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_stock_basicinfo(request)
    except Exception as e:
        logger.error(f"获取股票基本信息失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票基本信息失败: {e}", data=None)


@app.post("/api/quote/trading_days", 
          operation_id="get_trading_days",
          summary="获取交易日",
          description="获取指定市场在指定时间段内的交易日列表")
async def get_trading_days(request: TradingDaysRequest) -> APIResponse:
    """获取交易日 - 查询指定时间段内的交易日"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_trading_days(request)
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取交易日历失败: {e}", data=None)


@app.post("/api/quote/capital_flow", 
          operation_id="get_capital_flow",
          summary="获取资金流向",
          description="获取个股资金流向数据，包括主力、大单、中单、小单的净流入情况")
async def get_capital_flow(request: CapitalFlowRequest) -> APIResponse:
    """获取资金流向 - 分析主力资金动向和散户情绪"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_capital_flow(request)
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取资金流向失败: {e}", data=None)


@app.post("/api/quote/capital_distribution", 
          operation_id="get_capital_distribution",
          summary="获取资金分布",
          description="获取个股当前资金分布情况，分析特大单、大单、中单、小单的流入流出对比")
async def get_capital_distribution(request: CapitalDistributionRequest) -> APIResponse:
    """获取资金分布"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_capital_distribution(request)
    except Exception as e:
        logger.error(f"获取资金分布异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取资金分布异常: {str(e)}")


@app.post("/api/quote/rehab", 
          operation_id="get_rehab",
          summary="获取复权因子",
          description="获取股票复权因子数据，包括拆股、合股、送股、转增股、配股、增发等公司行为的复权信息")
async def get_rehab(request: RehabRequest) -> APIResponse:
    """获取复权因子"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_rehab(request)
    except Exception as e:
        logger.error(f"获取复权因子异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取复权因子异常: {str(e)}")


@app.post("/api/market/stock_filter", 
          operation_id="get_stock_filter",
          summary="条件选股",
          description="基于多种条件筛选股票，支持价格、成交量、技术指标等多维度筛选，支持板块过滤")
async def get_stock_filter(request: StockFilterRequest) -> APIResponse:
    """条件选股"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_stock_filter(request)
    except Exception as e:
        logger.error(f"条件选股异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"条件选股异常: {str(e)}")


@app.post("/api/market/plate_stock", 
          operation_id="get_plate_stock",
          summary="获取板块内股票列表",
          description="获取指定板块内的所有股票列表，支持按字段排序")
async def get_plate_stock(request: PlateStockRequest) -> APIResponse:
    """获取板块内股票列表"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_plate_stock(request)
    except Exception as e:
        logger.error(f"获取板块内股票列表异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取板块内股票列表异常: {str(e)}")


@app.post("/api/market/plate_list", 
          operation_id="get_plate_list",
          summary="获取板块列表",
          description="获取指定市场的板块列表，支持按板块类型过滤（行业、概念、地域板块）")
async def get_plate_list(request: PlateListRequest) -> APIResponse:
    """获取板块列表"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_plate_list(request)
    except Exception as e:
        logger.error(f"获取板块列表异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取板块列表异常: {str(e)}")


# ==================== 交易相关接口 ====================

@app.post("/api/trade/acc_info",
          operation_id="get_acc_info", 
          summary="查询账户资金",
          description="查询交易业务账户的资产净值、证券市值、现金、购买力等资金数据")
async def get_acc_info(request: AccInfoRequest) -> APIResponse:
    """查询账户资金 - 获取账户总资产、现金、购买力等资金信息"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await futu_service.get_acc_info(request)
    except Exception as e:
        logger.error(f"查询账户资金异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        
        raise HTTPException(status_code=500, detail=f"查询账户资金失败: {error_msg}")


@app.post("/api/trade/position_list",
          operation_id="get_position_list",
          summary="查询持仓列表", 
          description="查询交易业务账户的持仓列表，支持代码过滤、市场过滤、盈亏比例过滤等多种筛选条件")
async def get_position_list(request: PositionListRequest) -> APIResponse:
    """查询持仓列表 - 获取账户所有持仓信息，包含盈亏分析和市场分布"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await futu_service.get_position_list(request)
    except Exception as e:
        logger.error(f"查询持仓列表异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        elif "持仓" in error_msg:
            error_msg = "持仓数据获取失败，请检查账户是否有持仓或网络连接"
        
        raise HTTPException(status_code=500, detail=f"查询持仓列表失败: {error_msg}")


@app.post("/api/trade/history_deal_list",
          operation_id="get_history_deal_list",
          summary="查询历史成交", 
          description="查询交易业务账户的历史成交列表，支持代码过滤、市场过滤、时间范围过滤。注意：仅支持真实环境")
async def get_history_deal_list(request: HistoryDealListRequest) -> APIResponse:
    """查询历史成交 - 获取账户历史成交记录，包含买卖分析和费用统计"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await futu_service.get_history_deal_list(request)
    except Exception as e:
        logger.error(f"查询历史成交异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        elif "历史成交" in error_msg or "成交" in error_msg:
            error_msg = "历史成交数据获取失败，请检查时间范围或账户权限"
        elif "模拟" in error_msg:
            error_msg = "历史成交查询仅支持真实环境，不支持模拟环境"
        
        raise HTTPException(status_code=500, detail=f"查询历史成交失败: {error_msg}")


@app.post("/api/trade/deal_list",
          operation_id="get_deal_list",
          summary="查询当日成交", 
          description="查询交易业务账户的当日成交列表，支持代码过滤、市场过滤，包含实时成交统计")
async def get_deal_list(request: DealListRequest) -> APIResponse:
    """查询当日成交 - 获取账户当日成交记录，包含买卖分析和时间分布"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await futu_service.get_deal_list(request)
    except Exception as e:
        logger.error(f"查询当日成交异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        elif "当日成交" in error_msg or "成交" in error_msg:
            error_msg = "当日成交数据获取失败，请检查账户权限或网络连接"
        
        raise HTTPException(status_code=500, detail=f"查询当日成交失败: {error_msg}")


@app.post("/api/trade/history_order_list",
          operation_id="get_history_order_list",
          summary="获取历史订单列表",
          description="查询指定时间段内的历史订单记录，支持多种过滤条件")
async def get_history_order_list(request: HistoryOrderListRequest) -> APIResponse:
    """获取历史订单列表"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not futu_service or not futu_service.has_trade_connection():
        return APIResponse(ret_code=-1, ret_msg="交易接口未连接或未解锁，请检查OpenD状态后重试", data=None)
    
    try:
        return await futu_service.get_history_order_list(request)
    except Exception as e:
        logger.error(f"获取历史订单列表失败: {e}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        
        return APIResponse(ret_code=-1, ret_msg=f"获取历史订单列表失败: {error_msg}", data=None)


@app.post("/api/trade/order_fee_query",
          operation_id="get_order_fee_query",
          summary="查询订单费用",
          description="查询指定订单的详细费用信息，包括佣金、印花税等")
async def get_order_fee_query(request: OrderFeeQueryRequest) -> APIResponse:
    """查询订单费用"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not futu_service or not futu_service.has_trade_connection():
        return APIResponse(ret_code=-1, ret_msg="交易接口未连接或未解锁，请检查OpenD状态后重试", data=None)
    
    try:
        return await futu_service.get_order_fee_query(request)
    except Exception as e:
        logger.error(f"查询订单费用失败: {e}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "订单" in error_msg:
            error_msg = "订单信息有误，请检查订单ID是否正确"
        
        return APIResponse(ret_code=-1, ret_msg=f"查询订单费用失败: {error_msg}", data=None)


@app.post("/api/trade/trade_history",
          operation_id="get_trade_history",
          summary="获取交易历史",
          description="获取历史成交记录（history_deal_list的别名接口）")
async def get_trade_history(request: HistoryDealListRequest) -> APIResponse:
    """获取交易历史（历史成交的别名）"""
    return await get_history_deal_list(request)


# ==================== MCP实时看板接口 ====================
@app.post("/api/dashboard/session",
          operation_id="create_dashboard_session",
          summary="创建股票实时看板会话",
          description="生成一个可分享的 Web 看板 URL，用于实时查看指定股票的行情/资讯/策略",
          tags=["dashboard"])
async def create_dashboard_session(request: DashboardSessionRequest, http_request: Request) -> DashboardSessionResponse:
    if not _server_ready:
        raise HTTPException(status_code=503, detail="服务尚未就绪")
    session_id = secrets.token_urlsafe(10)
    async with _dashboard_lock:
        existing_session_id = None
        for sid, info in dashboard_sessions.items():
            if info.get("code") == request.code:
                existing_session_id = sid
                if request.nickname:
                    info["nickname"] = request.nickname
                break
        if existing_session_id:
            dashboard_sessions[existing_session_id].setdefault("history", [])
            session_id = existing_session_id
        else:
            dashboard_sessions[session_id] = {
                "code": request.code,
                "nickname": request.nickname,
                "created_at": datetime.now().isoformat(),
                "history": []
            }
    await _persist_dashboard_sessions()
    base_url = settings.dashboard_base_url.rstrip("/")
    url = f"{base_url}/web/dashboard?session={session_id}"
    if dashboard_stream_manager:
        dashboard_stream_manager.register_session(session_id, request.code)
        await dashboard_stream_manager.ensure_code_subscription(code=request.code)
        dashboard_stream_manager.start_guard()
    logger.info(f"[dashboard.session.create] session={session_id} code={request.code} nickname={request.nickname} reused={existing_session_id is not None}")
    return DashboardSessionResponse(session_id=session_id, url=url)


@app.get("/api/dashboard/sessions",
         operation_id="list_dashboard_sessions",
         summary="列出所有看板会话",
         tags=["dashboard"])
async def list_dashboard_sessions() -> Dict[str, Any]:
    start = time.time()
    removed_duplicates: List[Tuple[str, str]] = []
    async with _dashboard_lock:
        removed_duplicates = _remove_duplicate_sessions_locked()
        session_items = [
            DashboardSessionItem(
                session_id=session_id,
                code=info.get("code"),
                nickname=info.get("nickname"),
                created_at=info.get("created_at"),
            )
            for session_id, info in dashboard_sessions.items()
        ]
    if removed_duplicates:
        await _persist_dashboard_sessions()
        if dashboard_stream_manager:
            for session_id, code in removed_duplicates:
                await dashboard_stream_manager.unregister_session(session_id)
                await dashboard_stream_manager.force_detach_session(session_id)
        logger.warning(f"[dashboard.sessions.dedup] removed={len(removed_duplicates)} codes={[c for _, c in removed_duplicates]}")
    quota = None
    if futu_service:
        summary = await futu_service.get_subscription_summary()
        if summary.ret_code == 0 and isinstance(summary.data, dict):
            raw_quota = summary.data
            total_used = raw_quota.get("total_used") or raw_quota.get("totalUsed") or raw_quota.get("used") or 0
            remain = raw_quota.get("remain") or raw_quota.get("remainQuota") or raw_quota.get("remain_count") or 0
            own_used = raw_quota.get("own_used") or raw_quota.get("ownUsed") or raw_quota.get("self_used") or 0
            quota = {
                "total_used": total_used,
                "remain": remain,
                "own_used": own_used,
                "raw": raw_quota
            }
        # 获取行情快照 + 最新策略
        for item in session_items:
            quote = await _fetch_quote_snapshot(item.code)
            if quote:
                item.quote = quote
            if recommendation_storage:
                rec_req = RecommendationQueryRequest(code=item.code, limit=1)
                recs = await asyncio.to_thread(recommendation_storage.get_recommendations, rec_req.dict())
                if recs:
                    latest = recs[0]
                    item.strategy = latest.get("action")
                    item.last_signal_time = latest.get("created_at")
    cost = time.time() - start
    logger.info(f"[dashboard.sessions.list] total={len(session_items)} quota={'y' if quota else 'n'} cost={cost:.3f}s")
    return {"sessions": [item.model_dump() for item in session_items], "quota": quota}


@app.delete("/api/dashboard/session/{session_id}",
            operation_id="delete_dashboard_session",
            summary="删除看板会话",
            tags=["dashboard"])
async def delete_dashboard_session(session_id: str) -> Dict[str, Any]:
    async with _dashboard_lock:
        info = dashboard_sessions.pop(session_id, None)
    if not info:
        raise HTTPException(status_code=404, detail="session not found")
    await _persist_dashboard_sessions()
    if dashboard_stream_manager:
        await dashboard_stream_manager.unregister_session(session_id)
        await dashboard_stream_manager.force_detach_session(session_id)
    return {"deleted": True, "session_id": session_id, "code": info.get("code")}


DEFAULT_DASHBOARD_MODULES = {"core", "signals", "recommendations", "capital", "kline"}


@app.get("/api/dashboard/bootstrap",
         operation_id="get_dashboard_bootstrap",
         summary="获取看板初始数据",
         tags=["dashboard"])
async def get_dashboard_bootstrap(session: str, modules: Optional[str] = None) -> Dict[str, Any]:
    data = _ensure_dashboard_session(session)
    code = data["code"]
    module_set = (
        {m.strip().lower() for m in modules.split(",") if m.strip()} if modules else set(DEFAULT_DASHBOARD_MODULES)
    )
    module_set &= DEFAULT_DASHBOARD_MODULES
    if not module_set:
        module_set = set(DEFAULT_DASHBOARD_MODULES)

    start = time.time()
    logger.info(f"[dashboard.bootstrap] session={session} code={code} modules={','.join(sorted(module_set))}")

    def _noop_task(result=None):
        return asyncio.create_task(asyncio.sleep(0, result=result))

    tasks: Dict[str, asyncio.Task] = {}
    if "core" in module_set:
        tasks["quote"] = asyncio.create_task(_fetch_quote_snapshot(code))
        tasks["holding"] = asyncio.create_task(_fetch_holding_snapshot(code))
    if "signals" in module_set:
        tasks["signals"] = asyncio.create_task(_fetch_news_signals(code, 12, refresh=False))
    if "recommendations" in module_set:
        tasks["recommendations"] = asyncio.create_task(_fetch_recommendations_snapshot(code))
    if "capital" in module_set:
        if futu_service:
            start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            tasks["capital_flow"] = asyncio.create_task(
                futu_service.get_capital_flow(
                    CapitalFlowRequest(code=code, period_type=PeriodType.DAY, start=start_date)
                )
            )
            tasks["capital_distribution"] = asyncio.create_task(
                futu_service.get_capital_distribution(CapitalDistributionRequest(code=code))
            )
        else:
            tasks["capital_flow"] = _noop_task()
            tasks["capital_distribution"] = _noop_task()
    if "kline" in module_set:
        if futu_service:
            tasks["history_kline"] = asyncio.create_task(
                futu_service.get_history_kline(HistoryKLineRequest(code=code, ktype=KLType.K_1M, max_count=240))
            )
            tasks["current_kline"] = asyncio.create_task(
                futu_service.get_current_kline(
                    CurrentKLineRequest(code=code, num=240, ktype=KLType.K_1M, autype=AuType.QFQ)
                )
            )
        else:
            tasks["history_kline"] = _noop_task()
            tasks["current_kline"] = _noop_task()

    if tasks:
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    def _task_result(key: str):
        task = tasks.get(key)
        if not task:
            return None
        if task.cancelled():
            logger.warning(f"[dashboard.module.cancelled] session={session} module={key}")
            return None
        exc = task.exception()
        if exc:
            logger.warning(f"[dashboard.module.error] session={session} module={key} error={exc}")
            return None
        try:
            return task.result()
        except Exception as task_exc:
            logger.warning(f"[dashboard.module.result_error] session={session} module={key} error={task_exc}")
            return None

    history = data.get("history", [])
    bootstrap: Dict[str, Any] = {
        "code": code,
        "session": {
            "session_id": session,
            "nickname": data.get("nickname"),
            "created_at": data.get("created_at")
        },
        "history": history[-60:]
    }

    if "core" in module_set:
        quote = _task_result("quote")
        holding = _task_result("holding")
        session_window = _get_session_window(code)
        if quote:
            bootstrap["quote"] = quote
            if quote.get("prev_close") is not None:
                session_window["previous_close"] = quote.get("prev_close")
        if holding is not None:
            bootstrap["holding"] = holding
        bootstrap["session_window"] = session_window

    if "signals" in module_set and "signals" in tasks:
        signals_result = _task_result("signals")
        if signals_result is not None:
            bootstrap["signals"] = signals_result

    if "recommendations" in module_set and "recommendations" in tasks:
        rec_result = _task_result("recommendations")
        if rec_result is not None:
            bootstrap["recommendations"] = rec_result

    if "capital" in module_set:
        flow_resp = _task_result("capital_flow")
        distribution_resp = _task_result("capital_distribution")
        if flow_resp:
            if isinstance(flow_resp, APIResponse) and flow_resp.ret_code == 0:
                bootstrap["capital_flow"] = flow_resp.data
        if distribution_resp:
            if isinstance(distribution_resp, APIResponse) and distribution_resp.ret_code == 0:
                bootstrap["capital_distribution"] = distribution_resp.data

    if "kline" in module_set:
        history_result = _task_result("history_kline")
        current_result = _task_result("current_kline")
        history_data = (
            history_result.data.get("kline_data")
            if isinstance(history_result, APIResponse)
            and history_result.ret_code == 0
            and history_result.data
            else None
        )
        current_data = (
            current_result.data.get("kline_data")
            if isinstance(current_result, APIResponse)
            and current_result.ret_code == 0
            and current_result.data
            else None
        )
        merged_kline = _merge_kline_records(history_data, current_data)
        if minute_kline_storage and merged_kline:
            try:
                minute_kline_storage.save_batch(code, merged_kline)
                minute_kline_storage.delete_older_than(code, keep_limit=2880)
                stored_recent = minute_kline_storage.fetch_recent(code, limit=720)
                merged_kline = _merge_kline_records(stored_recent, merged_kline)
            except Exception as exc:
                logger.warning(f"分钟K线存储失败: {exc}")
        if merged_kline:
            bootstrap["history_kline"] = merged_kline

    logger.info(
        f"[dashboard.bootstrap.done] session={session} code={code} modules={','.join(sorted(module_set))} cost={time.time()-start:.3f}s"
    )
    return bootstrap


@app.get("/web/api/stream/{session_id}", include_in_schema=False)
async def dashboard_stream(session_id: str):
    session = _ensure_dashboard_session(session_id)
    code = session["code"]
    
    if not dashboard_stream_manager:
        raise HTTPException(status_code=503, detail="Dashboard流功能不可用")
    
    queue = await dashboard_stream_manager.attach_session(session_id, code)
    
    async def event_generator():
        try:
            logger.info(f"[dashboard.stream.attach] session={session_id} code={code}")
            while True:
                payload = await queue.get()
                history = session.setdefault("history", [])
                quote = payload.get("quote")
                if quote:
                    history.append({"ts": payload.get("timestamp"), "price": quote.get("price")})
                    if len(history) > 180:
                        history.pop(0)
                try:
                    chunk = json.dumps(payload, ensure_ascii=False)
                    yield f"data: {chunk}\\n\\n"
                except Exception as exc:
                    logger.debug(f"dashboard stream encode error: {exc}")
        except asyncio.CancelledError:
            logger.debug("dashboard stream cancelled")
        except Exception as exc:
            logger.warning(f"dashboard stream error: {exc}")
        finally:
            await dashboard_stream_manager.release_stream(session_id)
            logger.info(f"[dashboard.stream.detach] session={session_id} code={code}")
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ==================== 策略建议记录接口 ====================
@app.post("/api/recommendations",
          operation_id="save_recommendation",
          summary="保存策略建议",
          description="记录针对某标的的操作建议、信心、依据等信息，用于后续复盘",
          tags=["recommendation"])
async def save_recommendation(request: RecommendationWriteRequest) -> APIResponse:
    """保存策略建议"""
    if recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    
    try:
        if request.status == "running":
            has_other = await asyncio.to_thread(recommendation_storage.has_running_strategy, request.code)
            if has_other:
                return APIResponse(ret_code=-1, ret_msg="该股票已有执行中的策略", data=None)
        saved = await asyncio.to_thread(recommendation_storage.save_recommendation, request.dict())
        if strategy_monitor and request.status == "running" and saved.get("id"):
            full = await asyncio.to_thread(recommendation_storage.get_recommendation, saved["id"])
            if full:
                await strategy_monitor.register_strategy(full)
        return APIResponse(ret_code=0, ret_msg="策略建议保存成功", data=saved)
    except Exception as e:
        logger.error(f"保存策略建议失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"策略建议保存失败: {e}", data=None)


@app.post("/api/recommendations/query",
          operation_id="get_recommendations",
          summary="查询策略建议",
          description="按股票代码、操作类型、采纳状态、时间区间等条件检索历史策略建议",
          tags=["recommendation"])
async def get_recommendations(request: RecommendationQueryRequest) -> APIResponse:
    """查询策略建议"""
    if recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    
    try:
        items = await asyncio.to_thread(recommendation_storage.get_recommendations, request.dict())
        return APIResponse(ret_code=0, ret_msg="查询成功", data={"items": items, "count": len(items)})
    except Exception as e:
        logger.error(f"查询策略建议失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略建议失败: {e}", data=None)


@app.get("/api/recommendations/{rec_id}",
         operation_id="get_recommendation_detail",
         summary="查询单条策略详情",
         tags=["recommendation"])
async def get_recommendation_detail(rec_id: int) -> APIResponse:
    if recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        item = await asyncio.to_thread(recommendation_storage.get_recommendation, rec_id)
        if not item:
            raise HTTPException(status_code=404, detail="策略不存在")
        return APIResponse(ret_code=0, ret_msg="查询成功", data=item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询策略详情失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略详情失败: {e}", data=None)


@app.get("/api/recommendations/{rec_id}/evaluations",
         operation_id="get_recommendation_evaluations",
         summary="查询策略评估历史",
         tags=["recommendation"])
async def get_recommendation_evaluations(rec_id: int) -> APIResponse:
    if recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        history = await asyncio.to_thread(recommendation_storage.get_evaluations, rec_id)
        return APIResponse(ret_code=0, ret_msg="查询成功", data={"items": history, "count": len(history)})
    except Exception as e:
        logger.error(f"查询策略评估历史失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略评估历史失败: {e}", data=None)


@app.get("/api/recommendations/{rec_id}/alerts",
         operation_id="get_recommendation_alerts",
         summary="查询策略盯盘告警",
         tags=["recommendation"])
async def get_recommendation_alerts(rec_id: int, limit: int = 50) -> APIResponse:
    if recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        alerts = await asyncio.to_thread(recommendation_storage.get_alerts, rec_id, limit)
        return APIResponse(ret_code=0, ret_msg="查询成功", data={"items": alerts, "count": len(alerts)})
    except Exception as e:
        logger.error(f"查询策略告警失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略告警失败: {e}", data=None)


@app.patch("/api/recommendations/{rec_id}",
           operation_id="update_recommendation",
           summary="更新策略建议状态",
           tags=["recommendation"])
async def update_recommendation(rec_id: int, request: RecommendationUpdateRequest) -> APIResponse:
    if recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        existing = await asyncio.to_thread(recommendation_storage.get_recommendation, rec_id)
        if not existing:
            raise HTTPException(status_code=404, detail="策略不存在")
        payload = request.dict(exclude_unset=True)
        new_status = payload.get("status")
        if new_status == "running":
            has_other = await asyncio.to_thread(
                recommendation_storage.has_running_strategy,
                existing["code"],
                rec_id,
            )
            if has_other:
                return APIResponse(ret_code=-1, ret_msg="该股票已有执行中的策略", data=None)
        updated = await asyncio.to_thread(recommendation_storage.update_recommendation, rec_id, payload)
        if not updated:
            raise HTTPException(status_code=404, detail="策略不存在")
        if strategy_monitor:
            if payload.get("status"):
                if payload["status"] == "running":
                    await strategy_monitor.register_strategy(updated)
                else:
                    await strategy_monitor.unregister_strategy(rec_id)
            elif updated.get("status") == "running" and any(
                key in payload for key in ["monitor_config", "entry_price", "target_price", "stop_loss"]
            ):
                await strategy_monitor.register_strategy(updated)
        return APIResponse(ret_code=0, ret_msg="更新成功", data=updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新策略失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"更新策略失败: {e}", data=None)


@app.post("/api/recommendations/{rec_id}/reevaluate",
          operation_id="reevaluate_recommendation",
          summary="重新评估策略",
          tags=["recommendation"])
async def reevaluate_recommendation(rec_id: int, request: RecommendationReevaluateRequest) -> APIResponse:
    if recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    if not _server_ready or not multi_model_service:
        return APIResponse(ret_code=-1, ret_msg="多模型分析服务不可用", data=None)
    try:
        item = await asyncio.to_thread(recommendation_storage.get_recommendation, rec_id)
        if not item:
            raise HTTPException(status_code=404, detail="策略不存在")
        code = item.get("code")
        if not code:
            return APIResponse(ret_code=-1, ret_msg="策略缺少股票代码", data=None)
        snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=code))
        context_text = _build_analysis_context_text(snapshot)
        result = await multi_model_service.run_analysis(
            code=code,
            models=request.models,
            judge_model=request.judge_model,
            context_text=context_text,
            context_snapshot=snapshot,
            question=request.question,
        )
        quote = result.get("context_snapshot", {}).get("quote") or snapshot.get("quote") or {}
        current_price = quote.get("price") or quote.get("cur_price")
        entry_price = item.get("entry_price")
        pnl_pct = None
        try:
            if entry_price is not None and current_price is not None:
                entry_val = float(entry_price)
                if entry_val != 0:
                    pnl_pct = (float(current_price) - entry_val) / entry_val
        except (TypeError, ValueError):
            pnl_pct = None
        summary = (
            result.get("judge", {}).get("result", {}).get("summary")
            or "多模型已完成最新评估"
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        update_payload: Dict[str, Any] = {
            "eval_status": "completed",
            "eval_summary": summary,
            "eval_generated_at": now_iso,
            "eval_pnl_pct": pnl_pct,
            "eval_detail": {"analysis": result},
        }
        updated = await asyncio.to_thread(
            recommendation_storage.update_recommendation, rec_id, update_payload
        )
        history_record = await asyncio.to_thread(
            recommendation_storage.add_evaluation_record,
            rec_id,
            summary=summary,
            pnl=pnl_pct,
            detail={"analysis": result} if result else None,
            models=request.models,
            judge_model=request.judge_model,
            created_at=now_iso,
        )
        return APIResponse(
            ret_code=0,
            ret_msg="重新评估完成",
            data={
                "analysis": result,
                "evaluation": {
                    "summary": summary,
                    "generated_at": now_iso,
                    "pnl_pct": pnl_pct,
                },
                "history_record": history_record,
                "updated": updated,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新评估策略失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"重新评估策略失败: {e}", data=None)


# ==================== 基本面搜索接口 ====================

@app.post("/api/fundamental/search",
          operation_id="get_fundamental_search",
          summary="🔍 基本面信息搜索",
          description="通过metaso搜索API获取股票相关基本面信息、新闻和分析")
async def get_fundamental_search(request: FundamentalSearchRequest) -> APIResponse:
    """基本面信息搜索"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用基本面搜索功能", data=None)
    
    try:
        # 调用基本面搜索服务
        result = await fundamental_service.search_fundamental_info(request)
        return APIResponse(
            ret_code=0,
            ret_msg="基本面搜索成功",
            data=result.dict()
        )
    except Exception as e:
        logger.error(f"基本面搜索失败: {e}")
        error_msg = str(e)
        if "网络" in error_msg or "连接" in error_msg:
            error_msg = "搜索服务网络连接失败，请稍后重试"
        elif "权限" in error_msg or "授权" in error_msg:
            error_msg = "搜索服务权限验证失败"
        elif "超时" in error_msg:
            error_msg = "搜索请求超时，请稍后重试"
        
        return APIResponse(ret_code=-1, ret_msg=f"基本面搜索失败: {error_msg}", data=None)


@app.post("/api/fundamental/stock_search",
          operation_id="get_stock_fundamental",
          summary="🔍 股票基本面搜索",
          description="搜索特定股票的基本面信息，自动构建搜索关键词")
async def get_stock_fundamental(request: dict) -> APIResponse:
    """股票基本面搜索 - 简化接口"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用基本面搜索功能", data=None)
    
    try:
        stock_code = request.get("stock_code", "")
        stock_name = request.get("stock_name", "")
        
        if not stock_code:
            return APIResponse(ret_code=-1, ret_msg="股票代码不能为空", data=None)
        
        # 调用股票基本面搜索服务
        return await fundamental_service.search_stock_fundamental(stock_code, stock_name)
        
    except Exception as e:
        logger.error(f"股票基本面搜索失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"股票基本面搜索失败: {str(e)}", data=None)


@app.post("/api/fundamental/news/refresh",
          operation_id="refresh_fundamental_news",
          summary="刷新基本面资讯",
          description="根据指定数量重新抓取 Metaso 资讯并更新本地存储")
async def refresh_fundamental_news(request: FundamentalNewsRefreshRequest) -> APIResponse:
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用基本面搜索功能", data=None)
    try:
        signals = await _fetch_news_signals(request.code, request.size, days=request.days)
        return APIResponse(ret_code=0, ret_msg="刷新成功", data={"signals": signals})
    except Exception as e:
        logger.error(f"刷新基本面资讯失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"刷新基本面资讯失败: {e}", data=None)


@app.post("/api/fundamental/read_webpage",
          operation_id="read_webpage",
          summary="📄 读取网页内容",
          description="通过metaso reader API读取任意网页的纯文本内容")
async def read_webpage_endpoint(request: dict) -> APIResponse:
    """读取网页内容"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用网页读取功能", data=None)
    
    try:
        url = request.get("url", "")
        if not url:
            return APIResponse(ret_code=-1, ret_msg="网页URL不能为空", data=None)
        
        # 调用网页读取服务
        content = await fundamental_service.read_webpage(url)
        
        return APIResponse(
            ret_code=0,
            ret_msg="网页读取成功",
            data={
                "url": url,
                "content": content,
                "content_length": len(content),
                "api_source": "metaso"
            }
        )
        
    except Exception as e:
        logger.error(f"网页读取失败: {e}")
        error_msg = str(e)
        if "网络" in error_msg or "连接" in error_msg:
            error_msg = "网页读取网络连接失败，请稍后重试"
        elif "404" in error_msg:
            error_msg = "网页不存在或无法访问"
        elif "超时" in error_msg:
            error_msg = "网页读取超时，请稍后重试"
        
        return APIResponse(ret_code=-1, ret_msg=f"网页读取失败: {error_msg}", data=None)


@app.post("/api/fundamental/chat",
          operation_id="chat_completion",
          summary="💬 智能问答",
          description="通过metaso chat API进行智能问答对话")
async def chat_endpoint(request: dict) -> APIResponse:
    """智能问答"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用智能问答功能", data=None)
    
    try:
        messages = request.get("messages", [])
        model = request.get("model", "fast")
        stream = request.get("stream", True)
        
        if not messages:
            return APIResponse(ret_code=-1, ret_msg="对话消息不能为空", data=None)
        
        # 转换消息格式
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            else:
                formatted_messages.append({
                    "role": "user",
                    "content": str(msg)
                })
        
        # 调用问答服务
        answer = await fundamental_service.chat_completion(formatted_messages, model, stream)
        
        return APIResponse(
            ret_code=0,
            ret_msg="问答成功",
            data={
                "answer": answer,
                "model": model,
                "stream": stream,
                "messages": formatted_messages,
                "api_source": "metaso"
            }
        )
        
    except Exception as e:
        logger.error(f"问答失败: {e}")
        error_msg = str(e)
        if "网络" in error_msg or "连接" in error_msg:
            error_msg = "问答服务网络连接失败，请稍后重试"
        elif "权限" in error_msg or "授权" in error_msg:
            error_msg = "问答服务权限验证失败"
        elif "超时" in error_msg:
            error_msg = "问答请求超时，请稍后重试"
        
        return APIResponse(ret_code=-1, ret_msg=f"问答失败: {error_msg}", data=None)


# ==================== 注意事项 ====================
# 注意：富途API中没有"持仓历史"接口，持仓历史需要通过历史成交数据计算得出
# 当前持仓只能通过 position_list_query 获取当前时点的持仓信息

# ==================== MCP专用增强拉取接口 ====================

@app.post("/api/quote/realtime_quote_enhanced",
          operation_id="get_realtime_quote_enhanced",
          summary="🚀 MCP专用：增强实时报价拉取",
          description="专为MCP设计的实时报价接口，支持批量获取，无需订阅，直接拉取最新数据")
async def get_realtime_quote_enhanced(request: RealtimeQuoteEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时报价拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_quote_enhanced(request.codes, request.fields)
    except Exception as e:
        logger.error(f"获取增强实时报价失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时报价失败: {e}", data=None)


@app.post("/api/quote/realtime_orderbook_enhanced",
          operation_id="get_realtime_orderbook_enhanced",
          summary="🚀 MCP专用：增强实时摆盘拉取",
          description="专为MCP设计的实时摆盘接口，无需订阅，直接拉取买卖盘口数据")
async def get_realtime_orderbook_enhanced(request: RealtimeOrderBookEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时摆盘拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_orderbook_enhanced(request.code, request.num)
    except Exception as e:
        logger.error(f"获取增强实时摆盘失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时摆盘失败: {e}", data=None)


@app.post("/api/quote/realtime_ticker_enhanced",
          operation_id="get_realtime_ticker_enhanced",
          summary="🚀 MCP专用：增强实时逐笔拉取",
          description="专为MCP设计的实时逐笔接口，无需订阅，直接拉取最新成交数据")
async def get_realtime_ticker_enhanced(request: RealtimeTickerEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时逐笔拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_ticker_enhanced(request.code, request.num)
    except Exception as e:
        logger.error(f"获取增强实时逐笔失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时逐笔失败: {e}", data=None)


@app.post("/api/quote/realtime_data_enhanced",
          operation_id="get_realtime_data_enhanced",
          summary="🚀 MCP专用：增强实时分时拉取",
          description="专为MCP设计的实时分时接口，无需订阅，直接拉取分时走势数据")
async def get_realtime_data_enhanced(request: RealtimeDataEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时分时拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_data_enhanced(request.code)
    except Exception as e:
        logger.error(f"获取增强实时分时失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时分时失败: {e}", data=None)


# ==================== 启动配置 ====================
# 注释掉原来的MCP创建代码，移到lifespan中
# mcp = FastApiMCP(
#     app,
#     name="富途证券增强版MCP服务",
#     description="增强版富途证券API服务，集成15+技术指标、智能缓存系统、专业量化分析功能。支持港股、美股、A股实时报价，K线数据，技术分析指标计算，智能缓存优化，交易历史查询等功能。注意：持仓历史需通过历史成交数据计算。"
# )
# 
# # 挂载MCP服务到FastAPI应用
# mcp.mount()

if __name__ == "__main__":
    logger.info("🚀 启动富途MCP增强服务...")
    logger.info("📊 Web 总览: http://localhost:8001/web  (若自定义了 DASHBOARD_BASE_URL，请替换成对应域名)")
    
    uvicorn.run(
        "main_enhanced:app",
        host="0.0.0.0",
        port=8001,  # 使用不同端口避免冲突
        reload=False,  # 关闭reload避免初始化问题
        log_level="info"
    )
def _merge_kline_records(left: Optional[List[Dict[str, Any]]], right: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not left and not right:
        return []
    if not left:
        return list(right or [])
    if not right:
        return list(left or [])
    merged: Dict[str, Dict[str, Any]] = {}
    for record in left:
        key = record.get("time_key") or record.get("time")
        if not key:
            continue
        merged[key] = dict(record)
    for record in right:
        key = record.get("time_key") or record.get("time")
        if not key:
            continue
        base = merged.get(key, {})
        base.update(record)
        merged[key] = base
    sorted_items = sorted(merged.items(), key=lambda item: item[0])
    return [item[1] for item in sorted_items]


def _build_analysis_context_text(snapshot: Dict[str, Any]) -> str:
    quote = snapshot.get("quote") or {}
    session = snapshot.get("session_window") or {}
    capital_flow = (snapshot.get("capital_flow") or {}).get("summary", {})
    capital_distribution = (snapshot.get("capital_distribution") or {}).get("summary", {})
    insights = snapshot.get("insights") or {}
    generated_at = snapshot.get("generated_at")
    missing_parts: List[str] = []
    lines = []
    if quote:
        lines.append(
            f"[行情 @ {quote.get('update_time') or generated_at}] 价格 {quote.get('price') or quote.get('cur_price')}，"
            f"涨跌幅 {quote.get('change_rate')}%，成交额 {quote.get('turnover')}，成交量 {quote.get('volume')}。"
        )
    holding = snapshot.get("holding") or {}
    if holding:
        parts = [f"{k}:{v}" for k, v in holding.items()]
        lines.append("持仓: " + " / ".join(parts))
    else:
        missing_parts.append("持仓明细")

    if session:
        break_info = ""
        if session.get("break_start") and session.get("break_end"):
            break_info = f"，午休 {session['break_start']}~{session['break_end']}"
        lines.append(
            f"交易时段: {session.get('market','未知市场')} {session.get('open_time')}~{session.get('close_time')}{break_info}"
        )
    else:
        missing_parts.append("交易时段")

    signals = snapshot.get("signals") or {}
    for sentiment in ("bullish", "bearish"):
        items = signals.get(sentiment) or []
        if items:
            highlights = "; ".join(
                f"{(item.get('title') or item.get('summary') or '').strip()} [{item.get('publish_time') or item.get('published_at')}]"
                for item in items[:3]
                if item
            )
            label = "利好" if sentiment == "bullish" else "利空"
            lines.append(f"{label}资讯: {highlights}")
    if not any(signals.get(key) for key in ("bullish", "bearish", "neutral")):
        missing_parts.append("最新资讯/新闻")

    tech_summary = insights.get("technical_summary")
    if tech_summary:
        lines.append(f"技术摘要: {tech_summary}")
    if capital_flow:
        lines.append(
            f"资金流: {capital_flow.get('overall_trend')}，主力 {capital_flow.get('main_trend')}，"
            f"最新净流入 {capital_flow.get('latest_net_inflow')}"
        )
    else:
        missing_parts.append("资金流摘要")
    if capital_distribution:
        lines.append(
            f"资金分布: 主导资金 {capital_distribution.get('dominant_fund_type')} "
            f"{capital_distribution.get('dominant_fund_amount')}，总体 {capital_distribution.get('overall_trend')}"
        )
    recommendations = snapshot.get("recommendations") or []
    if recommendations:
        latest = recommendations[0]
        lines.append(
            f"最新策略: {latest.get('action')} ({latest.get('timeframe')}) "
            f"信心 {latest.get('confidence')} 于 {latest.get('created_at')}"
        )
    quote_counts = [insights.get("signal_bullish"), insights.get("signal_bearish"), insights.get("signal_neutral")]
    if any(v is not None for v in quote_counts):
        lines.append(
            f"信号分布: 利好 {insights.get('signal_bullish', '-')}"
            f" / 利空 {insights.get('signal_bearish', '-')}"
            f" / 中性 {insights.get('signal_neutral', '-')}"
        )
    if not quote:
        missing_parts.append("实时行情")
    if missing_parts:
        lines.append("⚠️ 数据缺口: " + "、".join(missing_parts))
    return "\n".join(lines)

class MultiModelAnalysisRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    models: List[str] = Field(default_factory=lambda: ["deepseek", "kimi"], description="参与分析的模型列表")
    judge_model: str = Field("gemini", description="最终评审模型")
    question: Optional[str] = Field(None, description="额外关注的问题")
