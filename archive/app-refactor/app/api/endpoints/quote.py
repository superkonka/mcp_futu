from fastapi import APIRouter, HTTPException
from app.models.futu import *
from app.services.futu_service import futu_service

router = APIRouter()

@router.post("/stock_quote", response_model=APIResponse)
async def get_stock_quote(request: StockQuoteRequest):
    return await futu_service.get_stock_quote(request)

@router.post("/history_kline", response_model=APIResponse)
async def get_history_kline(request: HistoryKLineRequest):
    return await futu_service.get_history_kline(request)

@router.post("/stock_basicinfo", response_model=APIResponse)
async def get_stock_basicinfo(request: StockBasicInfoRequest):
    return await futu_service.get_stock_basicinfo(request)
