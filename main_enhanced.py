#!/usr/bin/env python3
"""
富途MCP服务增强版 - 集成缓存和技术分析功能
支持智能缓存、技术指标计算、形态识别等高级功能
"""
from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S
from web_api.routes import analysis, system, quote, trade, dashboard, recommendations, fundamental



@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    
    logger.info("🚀 启动增强版MCP Futu服务...")
    
    try:
        # 初始化缓存管理器
        cache_config = CacheConfig(
            redis_url="redis://localhost:6379",
            sqlite_path="data/futu_cache.db",
            memory_max_size=2000,
            redis_expire_seconds=7200
        )
        S.cache_manager = DataCacheManager(cache_config)
        logger.info("✅ 缓存管理器初始化成功")
        
        S.recommendation_storage = RecommendationStorageService(db_path="data/recommendations.db")
        logger.info("✅ 策略建议存储服务初始化成功")
        S.dashboard_session_store = DashboardSessionStore(path="data/dashboard_sessions.json")
        logger.info("✅ 看板会话存储初始化成功")
        S.fundamental_storage = FundamentalNewsStorage(db_path="data/fundamental_news.db")
        logger.info("✅ 基本面资讯存储初始化成功")
        S.minute_kline_storage = MinuteKlineStorage(db_path="data/minute_kline.db")
        logger.info("✅ 分钟级K线存储初始化成功")
        if settings.deepseek_api_key:
            # 如果使用 Speciale base_url 且未指定模型，自动使用 special 模型名
            base_url = settings.deepseek_base_url or "https://api.deepseek.com/v1/chat/completions"
            is_speciale = "speciale" in (base_url or "").lower()
            default_model = "deepseek-v3.2-speciale" if is_speciale else "deepseek-chat"
            default_fundamental_model = default_model
            reasoner_model = (
                settings.deepseek_reasoner_model
                or getattr(settings, "deepseek_reaspmer_model", None)
                or "deepseek-reasoner"
            )
            S.deepseek_service = DeepSeekService(
                settings.deepseek_api_key,
                base_url=base_url,
                model=settings.deepseek_model or default_model,
                fundamental_model=settings.deepseek_fundamental_model or default_fundamental_model,
                reasoner_model=reasoner_model,
            )
            logger.info("✅ DeepSeek分析服务已启用")
        else:
            logger.warning("⚠️ DeepSeek API KEY 未配置，基本面高级分析不可用")
        S.multi_model_service = MultiModelAnalysisService(S.deepseek_service)
        
        # 初始化富途服务
        S.futu_service = FutuService()
        # 设置缓存管理器
        S.futu_service.cache_manager = S.cache_manager

        # 本地密钥检查（不影响服务启动，但提醒用户）
        if not settings.metaso_api_key:
            logger.warning("⚠️ Metaso API 密钥未配置。本地使用请在 .env 设置 METASO_API_KEY。")
        if not (settings.kimi_moonshot_key or settings.kimi_api_key):
            logger.warning("⚠️ Kimi API 密钥未配置。本地使用请在 .env 设置 KIMI_MOONSHOT_KEY。")
        
        # 尝试连接富途OpenD
        if await S.futu_service.connect():
            logger.info("✅ 富途OpenD连接成功")
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
        
        if S.dashboard_session_store:
            loaded_sessions = await asyncio.to_thread(S.dashboard_session_store.load)
            async with S._dashboard_lock:
                for session_id, info in loaded_sessions.items():
                    info.setdefault("history", [])
                    dashboard_sessions[session_id] = info
            logger.info(f"✅ 已恢复 {len(loaded_sessions)} 个看板会话")
        
        try:
            loop = asyncio.get_running_loop()
            S.dashboard_stream_manager = DashboardStreamManager(S.futu_service, loop, S.minute_kline_storage)
            if dashboard_sessions:
                for session_id, info in dashboard_sessions.items():
                    code = info.get("code")
                    if code:
                        S.dashboard_stream_manager.register_session(session_id, code)
                unique_codes = {sess["code"] for sess in dashboard_sessions.values() if sess.get("code")}
                for code in unique_codes:
                    await S.dashboard_stream_manager.ensure_code_subscription(code)
            S.dashboard_stream_manager.start_guard()
        except RuntimeError:
            logger.warning("未获取到事件循环，dashboard流功能不可用")
        
        S.strategy_monitor = StrategyMonitorService(S.futu_service, S.recommendation_storage)
        await S.strategy_monitor.start()

        # 等待服务完全初始化
        await asyncio.sleep(3)
        
        S._server_ready = True
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
        S._server_ready = False
        if S.futu_service:
            await S.futu_service.disconnect()
        if S.strategy_monitor:
            await S.strategy_monitor.stop()
        S.minute_kline_storage = None
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
    
    # 等待额外的初始化时间
    await asyncio.sleep(2)
    
    if not S._server_ready:
        logger.warning("⚠️  服务器初始化延迟，请稍后重试连接")
    else:
        logger.info("✅ Web API 服务已就绪")


# ==================== 健康检查 ====================
@app.get("/health")
async def health_check():
    """健康检查"""
    cache_stats = await S.cache_manager.get_cache_stats() if S.cache_manager else {}
    
    return {
        "status": "healthy" if S._server_ready else "degraded",
        "futu_connected": S._server_ready,
        "cache_available": S.cache_manager is not None,
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
        "server_ready": S._server_ready,
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


app.include_router(analysis.router)
app.include_router(system.router)
app.include_router(quote.router)
app.include_router(trade.router)
app.include_router(dashboard.router)
app.include_router(recommendations.router)
app.include_router(fundamental.router)
