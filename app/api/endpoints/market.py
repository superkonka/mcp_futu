from fastapi import APIRouter
import time
from datetime import datetime

router = APIRouter()

@router.get("/status")
async def market_status(market: str = "HK"):
    """获取市场状态"""
    now = datetime.now()
    hour = now.hour
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
