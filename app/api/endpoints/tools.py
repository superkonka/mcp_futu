from fastapi import APIRouter

router = APIRouter()

@router.get("/list")
async def list_tools():
    """列出可用工具"""
    return {
        "ret_code": 0,
        "ret_msg": "ok",
        "data": {
            "tools": [
                {"name": "get_stock_quote", "path": "/api/quote/stock_quote", "description": "获取股票报价"},
                {"name": "get_history_kline", "path": "/api/quote/history_kline", "description": "获取历史K线"},
                {"name": "get_technical_indicators", "path": "/api/analysis/technical_indicators", "description": "获取技术指标"}
            ]
        }
    }
