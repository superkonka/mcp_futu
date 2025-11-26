#!/usr/bin/env python3
"""
富途MCP服务增强版 - 无MCP依赖版本
专注于提供稳定的HTTP API服务
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, DefaultDict, Tuple
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
_sse_task: Optional[asyncio.Task] = None
_analysis_store: DefaultDict[str, List[Dict[str, Any]]] = DefaultDict(list)  # 简易内存存储：code -> AnalysisRecord 列表
_watchlist_store: DefaultDict[str, Set[str]] = DefaultDict(set)  # 简易内存存储：client_id -> codes 集合


# ==================== 订阅与推送管理器 ====================
class SubscriptionManager:
    """订阅管理器：管理客户端订阅与消息分发（单播）

    设计要点：
    - 每个客户端（client_id）维护一个独立的 asyncio.Queue 用于单播推送
    - 维护 client_id -> symbols 的映射，按需推送订阅到的标的
    - 提供心跳和断线清理，避免内存泄漏
    """

    def __init__(self):
        # 客户端消息队列：client_id -> asyncio.Queue
        self.client_queues: Dict[str, asyncio.Queue] = {}
        # 客户端订阅标的：client_id -> Set[symbol]
        self.client_symbols: DefaultDict[str, Set[str]] = DefaultDict(set)
        # 反向索引：symbol -> Set[client_id]
        self.symbol_clients: DefaultDict[str, Set[str]] = DefaultDict(set)
        # 最近心跳时间：client_id -> timestamp
        self.client_heartbeat: Dict[str, float] = {}
        # 读写锁，避免并发写入导致状态不一致
        self._lock = asyncio.Lock()

    async def register(self, client_id: str) -> asyncio.Queue:
        """注册客户端，返回其消息队列"""
        async with self._lock:
            if client_id not in self.client_queues:
                self.client_queues[client_id] = asyncio.Queue(maxsize=1000)
            self.client_heartbeat[client_id] = time.time()
            return self.client_queues[client_id]

    async def subscribe(self, client_id: str, symbols: List[str]):
        """为客户端添加订阅标的"""
        async with self._lock:
            # 确保队列存在
            if client_id not in self.client_queues:
                self.client_queues[client_id] = asyncio.Queue(maxsize=1000)
            # 更新映射
            for sym in symbols:
                self.client_symbols[client_id].add(sym)
                self.symbol_clients[sym].add(client_id)
            self.client_heartbeat[client_id] = time.time()

    async def unsubscribe_all(self, client_id: str):
        """取消客户端的所有订阅"""
        async with self._lock:
            for sym in list(self.client_symbols.get(client_id, set())):
                self.symbol_clients[sym].discard(client_id)
            self.client_symbols.pop(client_id, None)

    async def unregister(self, client_id: str):
        """注销客户端，清理资源"""
        async with self._lock:
            await self.unsubscribe_all(client_id)
            self.client_heartbeat.pop(client_id, None)
            q = self.client_queues.pop(client_id, None)
            if q:
                # 尝试放入结束信号，避免挂起
                try:
                    q.put_nowait({"type": "close"})
                except Exception:
                    pass

    async def broadcast_quotes(self, quotes: List[Dict[str, Any]]):
        """按订阅关系将报价单播到对应客户端队列"""
        if not quotes:
            return
        # 建立 code -> quote 的索引，便于快速匹配
        code_to_quote: Dict[str, Dict[str, Any]] = {}
        for q in quotes:
            code = q.get("code") or q.get("security") or q.get("symbol")
            if code:
                code_to_quote[code] = q

        async with self._lock:
            for code, quote in code_to_quote.items():
                clients = self.symbol_clients.get(code, set())
                if not clients:
                    continue
                payload = {
                    "type": "quote",
                    "code": code,
                    "quote": quote,
                    "timestamp": time.time()
                }
                for cid in list(clients):
                    q = self.client_queues.get(cid)
                    if q:
                        # 队列满则丢弃最旧消息，保证最新
                        if q.full():
                            try:
                                q.get_nowait()
                            except Exception:
                                pass
                        await q.put(payload)

    async def heartbeat(self, client_id: str):
        """更新客户端心跳"""
        async with self._lock:
            self.client_heartbeat[client_id] = time.time()

    async def cleanup_stale_clients(self, stale_after_sec: int = 60):
        """清理长时间无心跳的客户端"""
        now = time.time()
        async with self._lock:
            stale_ids = [cid for cid, ts in self.client_heartbeat.items() if now - ts > stale_after_sec]
            for cid in stale_ids:
                await self.unregister(cid)

    async def get_all_symbols(self) -> Set[str]:
        """获取当前所有被订阅的标的集合"""
        async with self._lock:
            return set(self.symbol_clients.keys())


subscription_manager = SubscriptionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global futu_service, cache_manager, _server_ready, _sse_task
    
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

        # 启动后台轮询任务：聚合订阅并单播推送SSE
        async def _poll_and_push_loop():
            """后台轮询富途报价并将结果按订阅单播推送到客户端

            策略：
            - 每 1 秒聚合一次当前订阅的全部标的
            - 使用现有 get_stock_quote 接口获取报价
            - 将结果按 client_id 订阅关系单播到对应队列
            - 同时推送心跳，清理无心跳的客户端
            """
            interval_sec = 1.0
            while True:
                try:
                    # 清理长时间无心跳客户端
                    await subscription_manager.cleanup_stale_clients(stale_after_sec=60)

                    # 聚合所有订阅标的
                    symbols = await subscription_manager.get_all_symbols()
                    if symbols:
                        # 调用已有服务获取报价
                        req = StockQuoteRequest(code_list=list(symbols))
                        resp = await futu_service.get_stock_quote(req)
                        if resp and resp.ret_code == 0 and resp.data:
                            quotes = resp.data.get("quotes", [])
                            await subscription_manager.broadcast_quotes(quotes)
                    # 控制轮询频率
                    await asyncio.sleep(interval_sec)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception(f"SSE后台轮询推送异常: {e}")
                    await asyncio.sleep(1.0)

        _sse_task = asyncio.create_task(_poll_and_push_loop())
            
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
        # 停止SSE后台任务
        if _sse_task:
            _sse_task.cancel()
            try:
                await _sse_task
            except Exception:
                pass


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


# ==================== 市场状态接口 ====================
@app.get("/api/market/status")
async def market_status(market: str = "HK") -> Dict[str, Any]:
    """获取市场状态（最小实现版）

    说明：
    - 简化判断：仅根据本地时间大致判断盘中，实际生产应接入交易所/OpenD日历
    - 返回字段与前端契约一致，便于后续替换为真实实现
    """
    now = datetime.now()
    hour = now.hour
    # 粗略盘中判断：9:00-16:00 视为 regular，其余为 after/pre
    is_open = 9 <= hour < 16
    session = "regular" if is_open else ("pre" if hour < 9 else "after")
    return {
        "ret_code": 0,
        "ret_msg": "ok",
        "data": {
            "is_open": is_open,
            "session": session,
            "market": market,
            "server_time": time.time()
        }
    }


# ==================== 分析历史与保存（最小实现） ====================
@app.get("/api/analysis/history")
async def analysis_history(code: str, limit: int = 20) -> Dict[str, Any]:
    """查询分析历史（内存版，便于前端联调）"""
    records = list(reversed(_analysis_store.get(code, [])))  # 时间倒序
    return {"ret_code": 0, "ret_msg": "ok", "data": records[: max(1, min(limit, 200))]}


@app.post("/api/analysis/save")
async def analysis_save(record: Dict[str, Any]) -> Dict[str, Any]:
    """保存分析结果（内存版）

    约定：
    - 若 record.id 为空，服务端生成简单ID；
    - 仅用于本地联调与前端打通，生产应落地数据库与鉴权。
    """
    code = record.get("code")
    if not code:
        return {"ret_code": 400, "ret_msg": "code 必填", "data": None}
    # 生成简易ID
    rec_id = record.get("id") or f"rec_{int(time.time()*1000)}"
    record["id"] = rec_id
    _analysis_store[code].append(record)
    return {"ret_code": 0, "ret_msg": "ok", "data": {"id": rec_id}}


def _normalize_kline_cache_scope(request: HistoryKLineRequest) -> Tuple[str, str, str]:
    """生成用于缓存的K线范围标识，保证不同请求互不干扰"""
    ktype_value = request.ktype.value if hasattr(request.ktype, "value") else str(request.ktype)
    autype_value = request.autype.value if hasattr(request.autype, "value") else str(request.autype)
    start_token = request.start or f"recent:{request.max_count}"
    end_token = request.end or "latest"
    return f"{ktype_value}:{autype_value}", start_token, end_token


# ==================== 信息拉取与来源状态（最小占位） ====================
@app.post("/api/info/fetch")
async def info_fetch(body: Dict[str, Any]) -> Dict[str, Any]:
    """信息来源聚合（占位实现）

    说明：返回结构与契约一致，便于前端打通；后续可接入真实新闻/公告/日历/技术/宏观源。
    """
    code = body.get("code")
    types: List[str] = body.get("types", [])
    if not code or not types:
        return {"ret_code": 400, "ret_msg": "code 与 types 必填", "data": None}
    data: Dict[str, Any] = {}
    now = time.time()
    for t in types:
        if t == "news":
            data["news"] = [{"title": "示例新闻", "ts": now, "summary": "这是一条示例新闻摘要"}]
        elif t == "filings":
            data["filings"] = [{"title": "示例公告", "ts": now, "highlights": ["营收增长", "利润改善"]}]
        elif t == "calendar":
            data["calendar"] = {"next_earnings": now + 86400 * 7}
        elif t == "tech":
            data["tech"] = {"rsi": 55.3, "macd": {"hist": 0.12}}
        elif t == "macro":
            data["macro"] = {"risk_index": 0.45}
        else:
            data[t] = None
    return {"ret_code": 0, "ret_msg": "ok", "data": data}


@app.get("/api/info/source_status")
async def info_source_status(code: str) -> Dict[str, Any]:
    """信息源更新时间状态（占位实现）"""
    now = time.time()
    return {
        "ret_code": 0,
        "ret_msg": "ok",
        "data": {
            "news_last_ts": now - 300,
            "filings_last_ts": now - 3600,
            "calendar_last_ts": now - 86400,
            "tech_last_ts": now - 120,
            "macro_last_ts": now - 7200,
            "stale": []
        }
    }


# ==================== LLM 分析聚合（最小占位网关） ====================
@app.post("/api/llm/analyze")
async def llm_analyze(req: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 分析聚合占位：统一输出结构，便于前端联调

    说明：
    - 当前直接返回一个规范化结构，可根据请求体决定是否需要更多信息；
    - 生产中应在服务端路由到具体模型（deepseek/kimi/豆包），注入系统指令并固化输出格式。
    """
    model = req.get("model", "deepseek")
    latest_quote = req.get("latestQuote", {})
    deltas = req.get("deltas", {})
    history = req.get("history", [])
    extra_info = req.get("extraInfo")

    # 简单规则：无额外信息时请求补充；有额外信息则给出等级
    need_more = extra_info is None
    resp = {
        "latest_basis": "示例：价格小幅上行，成交量放大，等待公告确认",
        "level": "observe" if need_more else "consider",
        "need_more_info": need_more,
        "info_requests": ["filings", "news"] if need_more else []
    }
    return {"ret_code": 0, "ret_msg": "ok", "data": resp}


# ==================== 关注列表接口（并联动订阅） ====================
@app.get("/api/watchlist")
async def get_watchlist(client_id: str) -> Dict[str, Any]:
    """获取账号级关注列表（内存版）"""
    codes = sorted(list(_watchlist_store.get(client_id, set())))
    return {"ret_code": 0, "ret_msg": "ok", "data": {"client_id": client_id, "codes": codes}}


@app.post("/api/watchlist/set")
async def set_watchlist(body: Dict[str, Any]) -> Dict[str, Any]:
    """设置账号级关注列表，并联动订阅绑定（覆盖语义）"""
    client_id = body.get("client_id")
    codes: List[str] = body.get("codes", [])
    if not client_id or not isinstance(codes, list):
        return {"ret_code": 400, "ret_msg": "client_id 与 codes 必填", "data": None}
    # 覆盖关注列表
    _watchlist_store[client_id] = set(codes)
    # 联动订阅（覆盖语义：先清空再订阅当前列表）
    await subscription_manager.unsubscribe_all(client_id)
    if codes:
        await subscription_manager.subscribe(client_id, codes)
    
    # 动态体现 OpenD 连接状态
    futu_connected = _server_ready and futu_service and futu_service.is_connected
    futu_status = "实时推送已就绪" if futu_connected else "等待数据源连接"
    
    return {
        "ret_code": 0, 
        "ret_msg": f"关注列表已更新并联动订阅，{futu_status}", 
        "data": {
            "client_id": client_id, 
            "codes": codes,
            "futu_connected": futu_connected
        }
    }

# ==================== SSE推送接口 ====================
@app.get("/api/stream/sse")
async def sse_stream(request: Request, client_id: str):
    """SSE流式推送端点（单播）

    用法：前端使用 EventSource(`/api/stream/sse?client_id=xxx`)
    - 服务器会将订阅到的标的报价以SSE事件单播给该client_id
    - 定期发送心跳，保持连接
    """

    # 注册并获取客户端队列
    queue = await subscription_manager.register(client_id)

    async def event_generator():
        # 初始欢迎事件
        welcome = {"type": "welcome", "client_id": client_id, "timestamp": time.time()}
        yield f"event: welcome\ndata: {json.dumps(welcome)}\n\n"

        # 循环读取队列并推送
        heartbeat_interval = 15
        last_heartbeat = time.time()
        try:
            while True:
                # 如果客户端断开连接，终止生成器
                if await request.is_disconnected():
                    break

                # 尝试从队列获取最新消息，带超时
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    payload = None

                # 推送业务消息
                if payload:
                    if payload.get("type") == "close":
                        break
                    yield f"event: quote\ndata: {json.dumps(payload)}\n\n"

                # 定期发送心跳，避免中间设备断流
                now = time.time()
                if now - last_heartbeat >= heartbeat_interval:
                    await subscription_manager.heartbeat(client_id)
                    yield f"event: heartbeat\ndata: {json.dumps({'ts': now})}\n\n"
                    last_heartbeat = now

        finally:
            # 连接断开时，清理资源
            await subscription_manager.unregister(client_id)

    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        # 避免nginx/proxy缓冲
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_generator(), headers=headers)


# ==================== 订阅控制接口（供前端调用） ====================
@app.post("/api/quote/subscribe_push")
async def subscribe_push(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """订阅推送接口：绑定 client_id 与 symbols

    请求示例：
    {
        "client_id": "frontend-123",
        "symbols": ["HK.00700", "US.AAPL"]
    }
    """
    client_id = request_body.get("client_id")
    symbols = request_body.get("symbols") or request_body.get("code_list") or []
    if not client_id or not isinstance(symbols, list) or not symbols:
        return {"ret_code": -1, "ret_msg": "参数不合法，需要 client_id 与 symbols 列表", "data": None}

    await subscription_manager.subscribe(client_id, symbols)
    
    # 动态体现 OpenD 连接状态
    futu_connected = _server_ready and futu_service and futu_service.is_connected
    futu_status = "实时推送已就绪" if futu_connected else "等待数据源连接"
    
    return {
        "ret_code": 0,
        "ret_msg": f"订阅已受理，{futu_status}",
        "data": {
            "client_id": client_id, 
            "symbols": symbols,
            "futu_connected": futu_connected
        }
    }

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
        ktype_token, cache_start, cache_end = _normalize_kline_cache_scope(request)
        # 1. 尝试从缓存获取数据
        if CACHE_AVAILABLE and cache_manager:
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
        if result.ret_code == 0 and CACHE_AVAILABLE and cache_manager and result.data.get("kline_data"):
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
