from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from app.services.subscription_service import subscription_manager
from app.services.futu_service import futu_service
import uuid
import json
import asyncio
import time
from datetime import datetime
from loguru import logger

router = APIRouter()

@router.post("/session")
async def create_session(request: Request):
    """创建新的看板会话"""
    body = await request.json()
    code = body.get("code")
    
    session_id = str(uuid.uuid4())
    metadata = {"code": code} if code else {}
    await subscription_manager.register(session_id, metadata)
    return {"session_id": session_id}

@router.get("/sessions")
async def get_sessions():
    """获取所有活跃会话"""
    # 1. 获取手动创建的会话
    sessions = await subscription_manager.get_all_sessions()
    existing_codes = {s.get("code") for s in sessions if s.get("code")}
    
    # 2. 获取持仓数据
    from app.models.futu import PositionListRequest, TrdEnv
    
    # 尝试获取真实环境持仓
    try:
        logger.info("Attempting to fetch REAL positions...")
        resp = await futu_service.get_position_list(PositionListRequest(trd_env=TrdEnv.REAL))
        if resp.ret_code == 0 and resp.data:
            positions = resp.data.get("position_list", [])
            logger.info(f"Found {len(positions)} REAL positions")
            
            for pos in positions:
                code = pos.get("code")
                if code:
                    session_id = f"pos_{code}"
                    if code not in existing_codes:
                        sessions.append({
                            "session_id": session_id,
                            "code": code,
                            "created_at": datetime.now().isoformat(),
                            "source": "position_real",
                            "holding": pos
                        })
                        existing_codes.add(code)
                    else:
                        for s in sessions:
                            if s.get("code") == code:
                                s["holding"] = pos
                                break
    except Exception as e:
        logger.error(f"Failed to fetch REAL positions: {e}")

    # 尝试获取模拟环境持仓 (如果真实环境没有或者作为补充)
    try:
        logger.info("Attempting to fetch SIMULATE positions...")
        resp = await futu_service.get_position_list(PositionListRequest(trd_env=TrdEnv.SIMULATE))
        if resp.ret_code == 0 and resp.data:
            positions = resp.data.get("position_list", [])
            logger.info(f"Found {len(positions)} SIMULATE positions")
            
            for pos in positions:
                code = pos.get("code")
                if code:
                    session_id = f"pos_{code}"
                    if code not in existing_codes:
                        sessions.append({
                            "session_id": session_id,
                            "code": code,
                            "created_at": datetime.now().isoformat(),
                            "source": "position_sim",
                            "holding": pos
                        })
                        existing_codes.add(code)
                    # 如果已存在（可能是真实环境的），则不覆盖，优先显示真实环境
    except Exception as e:
        logger.error(f"Failed to fetch SIMULATE positions: {e}")

    return {
        "sessions": sessions,
        "quota": {
            "total_used": len(sessions),
            "remain": 100 - len(sessions)
        }
    }

@router.get("/bootstrap")
async def get_bootstrap(session: str, modules: str = None):
    """获取初始数据"""
    if not session:
        raise HTTPException(status_code=400, detail="Missing session")
    
    code = None
    if session.startswith("pos_"):
        code = session[4:]
    else:
        # 尝试从现有元数据获取
        meta = subscription_manager.client_metadata.get(session)
        if meta:
            code = meta.get("code")
    
    # 注册会话 (更新心跳)
    metadata = {"code": code} if code else {}
    await subscription_manager.register(session, metadata)
    
    if code:
        # 自动订阅行情
        await subscription_manager.subscribe(session, [code])
    
    # 构建基础响应
    response_data = {
        "code": code or "",
        "session": {
            "session_id": session,
            "created_at": datetime.now().isoformat()
        }
    }
    
    if code:
        # 1. 获取报价
        from app.models.futu import StockQuoteRequest, PositionListRequest, TrdEnv
        try:
            quote_resp = await futu_service.get_stock_quote(StockQuoteRequest(code_list=[code]))
            if quote_resp.ret_code == 0 and quote_resp.data:
                quotes = quote_resp.data.get("quotes", [])
                if quotes:
                    response_data["quote"] = quotes[0]
        except Exception as e:
            logger.error(f"Bootstrap quote fetch error: {e}")

        # 2. 获取持仓 (如果是持仓会话)
        # 无论是否是pos_开头，都尝试获取持仓信息，万一用户手动添加的关注也是持仓呢
        try:
            # 优先尝试真实环境
            pos_resp = await futu_service.get_position_list(PositionListRequest(
                code=code, 
                trd_env=TrdEnv.REAL
            ))
            found_holding = False
            if pos_resp.ret_code == 0 and pos_resp.data:
                positions = pos_resp.data.get("position_list", [])
                if positions:
                    response_data["holding"] = positions[0]
                    found_holding = True
            
            # 如果真实环境没找到，尝试模拟环境
            if not found_holding:
                pos_resp = await futu_service.get_position_list(PositionListRequest(
                    code=code, 
                    trd_env=TrdEnv.SIMULATE
                ))
                if pos_resp.ret_code == 0 and pos_resp.data:
                    positions = pos_resp.data.get("position_list", [])
                    if positions:
                        response_data["holding"] = positions[0]
                        
        except Exception as e:
            logger.error(f"Bootstrap holding fetch error: {e}")
            
    return response_data

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    await subscription_manager.unregister(session_id)
    return {"status": "ok"}

@router.get("/sse/{session_id}")
async def sse_endpoint(session_id: str, request: Request):
    """SSE 实时推送"""
    queue = await subscription_manager.register(session_id)
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                try:
                    # 等待消息，超时发送心跳
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    
                    if payload.get("type") == "close":
                        break
                        
                    yield f"data: {json.dumps(payload)}\n\n"
                    
                except asyncio.TimeoutError:
                    # 发送心跳
                    await subscription_manager.heartbeat(session_id)
                    yield ": heartbeat\n\n"
                    
        except Exception as e:
            logger.error(f"SSE error for {session_id}: {e}")
        finally:
            await subscription_manager.unregister(session_id)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/subscribe")
async def subscribe(session_id: str, codes: list[str]):
    """订阅股票"""
    await subscription_manager.subscribe(session_id, codes)
    # 立即尝试获取一次报价并推送
    # 这里需要调用 futu_service 获取报价，然后通过 subscription_manager 推送
    # 由于 futu_service 和 subscription_manager 解耦，这里可以手动触发一次
    from app.models.futu import StockQuoteRequest, DataOptimization
    
    try:
        resp = await futu_service.get_stock_quote(StockQuoteRequest(code_list=codes))
        if resp.ret_code == 0 and resp.data:
            quotes = resp.data.get("quotes", [])
            await subscription_manager.broadcast_quotes(quotes)
    except Exception as e:
        logger.error(f"Initial quote fetch failed: {e}")
        
    return {"status": "ok"}
