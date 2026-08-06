"""策略建议记录接口 —— 从 main_enhanced.py 机械拆分，行为不变。"""
from fastapi import APIRouter

from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S  # 运行期全局（服务实例 / _server_ready）
from web_api.routes.analysis import get_analysis_snapshot  # 跨模块复用（原单文件内直接调用）

router = APIRouter()




# ==================== 策略建议记录接口 ====================
@router.post("/api/recommendations",
          operation_id="save_recommendation",
          summary="保存策略建议",
          description="记录针对某标的的操作建议、信心、依据等信息，用于后续复盘",
          tags=["recommendation"])
async def save_recommendation(request: RecommendationWriteRequest) -> APIResponse:
    """保存策略建议"""
    if S.recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    
    try:
        if request.status == "running":
            has_other = await asyncio.to_thread(S.recommendation_storage.has_running_strategy, request.code)
            if has_other:
                return APIResponse(ret_code=-1, ret_msg="该股票已有执行中的策略", data=None)
        saved = await asyncio.to_thread(S.recommendation_storage.save_recommendation, request.dict())
        if S.strategy_monitor and request.status == "running" and saved.get("id"):
            full = await asyncio.to_thread(S.recommendation_storage.get_recommendation, saved["id"])
            if full:
                await S.strategy_monitor.register_strategy(full)
        return APIResponse(ret_code=0, ret_msg="策略建议保存成功", data=saved)
    except Exception as e:
        logger.error(f"保存策略建议失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"策略建议保存失败: {e}", data=None)


@router.post("/api/recommendations/query",
          operation_id="get_recommendations",
          summary="查询策略建议",
          description="按股票代码、操作类型、采纳状态、时间区间等条件检索历史策略建议",
          tags=["recommendation"])
async def get_recommendations(request: RecommendationQueryRequest) -> APIResponse:
    """查询策略建议"""
    if S.recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    
    try:
        items = await asyncio.to_thread(S.recommendation_storage.get_recommendations, request.dict())
        return APIResponse(ret_code=0, ret_msg="查询成功", data={"items": items, "count": len(items)})
    except Exception as e:
        logger.error(f"查询策略建议失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略建议失败: {e}", data=None)


@router.get("/api/recommendations/{rec_id}",
         operation_id="get_recommendation_detail",
         summary="查询单条策略详情",
         tags=["recommendation"])
async def get_recommendation_detail(rec_id: int) -> APIResponse:
    if S.recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        item = await asyncio.to_thread(S.recommendation_storage.get_recommendation, rec_id)
        if not item:
            raise HTTPException(status_code=404, detail="策略不存在")
        return APIResponse(ret_code=0, ret_msg="查询成功", data=item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询策略详情失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略详情失败: {e}", data=None)


@router.get("/api/recommendations/{rec_id}/evaluations",
         operation_id="get_recommendation_evaluations",
         summary="查询策略评估历史",
         tags=["recommendation"])
async def get_recommendation_evaluations(rec_id: int) -> APIResponse:
    if S.recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        history = await asyncio.to_thread(S.recommendation_storage.get_evaluations, rec_id)
        return APIResponse(ret_code=0, ret_msg="查询成功", data={"items": history, "count": len(history)})
    except Exception as e:
        logger.error(f"查询策略评估历史失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略评估历史失败: {e}", data=None)


@router.get("/api/recommendations/{rec_id}/alerts",
         operation_id="get_recommendation_alerts",
         summary="查询策略盯盘告警",
         tags=["recommendation"])
async def get_recommendation_alerts(rec_id: int, limit: int = 50) -> APIResponse:
    if S.recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        alerts = await asyncio.to_thread(S.recommendation_storage.get_alerts, rec_id, limit)
        return APIResponse(ret_code=0, ret_msg="查询成功", data={"items": alerts, "count": len(alerts)})
    except Exception as e:
        logger.error(f"查询策略告警失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"查询策略告警失败: {e}", data=None)


@router.patch("/api/recommendations/{rec_id}",
           operation_id="update_recommendation",
           summary="更新策略建议状态",
           tags=["recommendation"])
async def update_recommendation(rec_id: int, request: RecommendationUpdateRequest) -> APIResponse:
    if S.recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    try:
        existing = await asyncio.to_thread(S.recommendation_storage.get_recommendation, rec_id)
        if not existing:
            raise HTTPException(status_code=404, detail="策略不存在")
        payload = request.dict(exclude_unset=True)
        new_status = payload.get("status")
        if new_status == "running":
            has_other = await asyncio.to_thread(
                S.recommendation_storage.has_running_strategy,
                existing["code"],
                rec_id,
            )
            if has_other:
                return APIResponse(ret_code=-1, ret_msg="该股票已有执行中的策略", data=None)
        updated = await asyncio.to_thread(S.recommendation_storage.update_recommendation, rec_id, payload)
        if not updated:
            raise HTTPException(status_code=404, detail="策略不存在")
        if S.strategy_monitor:
            if payload.get("status"):
                if payload["status"] == "running":
                    await S.strategy_monitor.register_strategy(updated)
                else:
                    await S.strategy_monitor.unregister_strategy(rec_id)
            elif updated.get("status") == "running" and any(
                key in payload for key in ["monitor_config", "entry_price", "target_price", "stop_loss"]
            ):
                await S.strategy_monitor.register_strategy(updated)
        return APIResponse(ret_code=0, ret_msg="更新成功", data=updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新策略失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"更新策略失败: {e}", data=None)


@router.post("/api/recommendations/{rec_id}/reevaluate",
          operation_id="reevaluate_recommendation",
          summary="重新评估策略",
          tags=["recommendation"])
async def reevaluate_recommendation(rec_id: int, request: RecommendationReevaluateRequest) -> APIResponse:
    if S.recommendation_storage is None:
        return APIResponse(ret_code=-1, ret_msg="策略建议存储服务未初始化", data=None)
    if not S._server_ready or not S.multi_model_service:
        return APIResponse(ret_code=-1, ret_msg="多模型分析服务不可用", data=None)
    try:
        item = await asyncio.to_thread(S.recommendation_storage.get_recommendation, rec_id)
        if not item:
            raise HTTPException(status_code=404, detail="策略不存在")
        code = item.get("code")
        if not code:
            return APIResponse(ret_code=-1, ret_msg="策略缺少股票代码", data=None)
        snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=code))
        context_text = S._build_analysis_context_text(snapshot)
        result = await S.multi_model_service.run_analysis(
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
            S.recommendation_storage.update_recommendation, rec_id, update_payload
        )
        history_record = await asyncio.to_thread(
            S.recommendation_storage.add_evaluation_record,
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
