from fastapi import APIRouter, HTTPException
from app.models.analysis import *
from app.models.futu import HistoryKLineRequest, KLType, AuType
from app.services.futu_service import futu_service
from app.services.analysis_service import analysis_service
import time

router = APIRouter()

@router.post("/technical_indicators", response_model=TechnicalAnalysisResponse)
async def get_technical_indicators(request: TechnicalAnalysisRequest):
    # 1. 获取K线数据
    kline_req = HistoryKLineRequest(
        code=request.code,
        ktype=KLType(request.ktype),
        max_count=request.period + 50, # 多取一些数据用于计算MA等
        autype=AuType.QFQ
    )
    
    resp = await futu_service.get_history_kline(kline_req)
    if resp.ret_code != 0 or not resp.data:
        raise HTTPException(status_code=400, detail=f"获取K线数据失败: {resp.ret_msg}")
        
    kline_data = resp.data.get("kline_data", [])
    if not kline_data:
        raise HTTPException(status_code=404, detail="未找到K线数据")
        
    # 2. 提取收盘价
    prices = [float(item['close']) for item in kline_data]
    
    # 3. 计算指标
    indicators_data = analysis_service.calculate(prices, request.indicators, request.params)
    
    # 4. 生成信号
    signals = analysis_service.analyze_signal(indicators_data)
    
    return TechnicalAnalysisResponse(
        code=request.code,
        timestamp=time.time(),
        indicators=indicators_data,
        signals=signals
    )
