"""MCP 实时看板接口 —— 从 main_enhanced.py 机械拆分，行为不变。"""
from fastapi import APIRouter

from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S  # 运行期全局（服务实例 / _server_ready）

router = APIRouter()




# ==================== MCP实时看板接口 ====================
@router.post("/api/dashboard/session",
          operation_id="create_dashboard_session",
          summary="创建股票实时看板会话",
          description="生成一个可分享的 Web 看板 URL，用于实时查看指定股票的行情/资讯/策略",
          tags=["dashboard"])
async def create_dashboard_session(request: DashboardSessionRequest, http_request: Request) -> DashboardSessionResponse:
    if not S._server_ready:
        raise HTTPException(status_code=503, detail="服务尚未就绪")
    session_id = secrets.token_urlsafe(10)
    async with S._dashboard_lock:
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
    await S._persist_dashboard_sessions()
    base_url = settings.dashboard_base_url.rstrip("/")
    url = f"{base_url}/web/dashboard?session={session_id}"
    if S.dashboard_stream_manager:
        S.dashboard_stream_manager.register_session(session_id, request.code)
        await S.dashboard_stream_manager.ensure_code_subscription(code=request.code)
        S.dashboard_stream_manager.start_guard()
    logger.info(f"[dashboard.session.create] session={session_id} code={request.code} nickname={request.nickname} reused={existing_session_id is not None}")
    return DashboardSessionResponse(session_id=session_id, url=url)


@router.get("/api/dashboard/sessions",
         operation_id="list_dashboard_sessions",
         summary="列出所有看板会话",
         tags=["dashboard"])
async def list_dashboard_sessions() -> Dict[str, Any]:
    start = time.time()
    removed_duplicates: List[Tuple[str, str]] = []
    async with S._dashboard_lock:
        removed_duplicates = S._remove_duplicate_sessions_locked()
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
        await S._persist_dashboard_sessions()
        if S.dashboard_stream_manager:
            for session_id, code in removed_duplicates:
                await S.dashboard_stream_manager.unregister_session(session_id)
                await S.dashboard_stream_manager.force_detach_session(session_id)
        logger.warning(f"[dashboard.sessions.dedup] removed={len(removed_duplicates)} codes={[c for _, c in removed_duplicates]}")
    quota = None
    if S.futu_service:
        summary = await S.futu_service.get_subscription_summary()
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
            quote = await S._fetch_quote_snapshot(item.code)
            if quote:
                item.quote = quote
            if S.recommendation_storage:
                rec_req = RecommendationQueryRequest(code=item.code, limit=1)
                recs = await asyncio.to_thread(S.recommendation_storage.get_recommendations, rec_req.dict())
                if recs:
                    latest = recs[0]
                    item.strategy = latest.get("action")
                    item.last_signal_time = latest.get("created_at")
    cost = time.time() - start
    logger.info(f"[dashboard.sessions.list] total={len(session_items)} quota={'y' if quota else 'n'} cost={cost:.3f}s")
    return {"sessions": [item.model_dump() for item in session_items], "quota": quota}


@router.delete("/api/dashboard/session/{session_id}",
            operation_id="delete_dashboard_session",
            summary="删除看板会话",
            tags=["dashboard"])
async def delete_dashboard_session(session_id: str) -> Dict[str, Any]:
    async with S._dashboard_lock:
        info = dashboard_sessions.pop(session_id, None)
    if not info:
        raise HTTPException(status_code=404, detail="session not found")
    await S._persist_dashboard_sessions()
    if S.dashboard_stream_manager:
        await S.dashboard_stream_manager.unregister_session(session_id)
        await S.dashboard_stream_manager.force_detach_session(session_id)
    return {"deleted": True, "session_id": session_id, "code": info.get("code")}


DEFAULT_DASHBOARD_MODULES = {"core", "signals", "recommendations", "capital", "kline"}


@router.get("/api/dashboard/bootstrap",
         operation_id="get_dashboard_bootstrap",
         summary="获取看板初始数据",
         tags=["dashboard"])
async def get_dashboard_bootstrap(session: str, modules: Optional[str] = None) -> Dict[str, Any]:
    data = S._ensure_dashboard_session(session)
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
    if "core" in module_set or "signals" in module_set:
        tasks["quote"] = asyncio.create_task(S._fetch_quote_snapshot(code))
    if "core" in module_set:
        tasks["holding"] = asyncio.create_task(S._fetch_holding_snapshot(code))
    if "recommendations" in module_set:
        tasks["recommendations"] = asyncio.create_task(S._fetch_recommendations_snapshot(code))
    if "capital" in module_set:
        if S.futu_service:
            start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            tasks["capital_flow"] = asyncio.create_task(
                S.futu_service.get_capital_flow(
                    CapitalFlowRequest(code=code, period_type=PeriodType.DAY, start=start_date)
                )
            )
            tasks["capital_distribution"] = asyncio.create_task(
                S.futu_service.get_capital_distribution(CapitalDistributionRequest(code=code))
            )
        else:
            tasks["capital_flow"] = _noop_task()
            tasks["capital_distribution"] = _noop_task()
    if "kline" in module_set:
        if S.futu_service:
            tasks["history_kline"] = asyncio.create_task(
                S.futu_service.get_history_kline(HistoryKLineRequest(code=code, ktype=KLType.K_1M, max_count=240))
            )
            tasks["current_kline"] = asyncio.create_task(
                S.futu_service.get_current_kline(
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
        session_window = S._get_session_window(code)
        if quote:
            bootstrap["quote"] = quote
            if quote.get("prev_close") is not None:
                session_window["previous_close"] = quote.get("prev_close")
        if holding is not None:
            bootstrap["holding"] = holding
        bootstrap["session_window"] = session_window

    if "signals" in module_set:
        # 需要公司名以便关键词过滤，本地信号不再乱跳
        stock_name = data.get("nickname")
        quote_for_signals = tasks.get("quote")
        if quote_for_signals and not quote_for_signals.cancelled():
            try:
                quote_val = quote_for_signals.result()
                if quote_val and quote_val.get("name"):
                    stock_name = quote_val.get("name")
            except Exception:
                pass
        signals_result = await S._fetch_news_signals(code, 12, refresh=False, stock_name=stock_name)
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
        merged_kline = S._merge_kline_records(history_data, current_data)
        if S.minute_kline_storage and merged_kline:
            try:
                S.minute_kline_storage.save_batch(code, merged_kline)
                S.minute_kline_storage.delete_older_than(code, keep_limit=2880)
                stored_recent = S.minute_kline_storage.fetch_recent(code, limit=720)
                merged_kline = S._merge_kline_records(stored_recent, merged_kline)
            except Exception as exc:
                logger.warning(f"分钟K线存储失败: {exc}")
        if merged_kline:
            bootstrap["history_kline"] = merged_kline

    logger.info(
        f"[dashboard.bootstrap.done] session={session} code={code} modules={','.join(sorted(module_set))} cost={time.time()-start:.3f}s"
    )
    return bootstrap


@router.get("/web/api/stream/{session_id}", include_in_schema=False)
async def dashboard_stream(session_id: str):
    session = S._ensure_dashboard_session(session_id)
    code = session["code"]
    
    if not S.dashboard_stream_manager:
        raise HTTPException(status_code=503, detail="Dashboard流功能不可用")
    
    queue = await S.dashboard_stream_manager.attach_session(session_id, code)
    
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
            await S.dashboard_stream_manager.release_stream(session_id)
            logger.info(f"[dashboard.stream.detach] session={session_id} code={code}")
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
