#!/usr/bin/env python3
"""
简化版技术指标API测试
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uvicorn
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analysis.technical_indicators import TechnicalIndicators, IndicatorConfig

app = FastAPI(title="技术指标API测试", version="1.0.0")

class SimpleIndicatorRequest(BaseModel):
    code: str
    period: int = 14
    indicators: List[str] = ["macd", "rsi"]

class SimpleIndicatorResponse(BaseModel):
    code: str
    period: int
    indicators: Dict[str, Any]
    timestamp: str

@app.post("/test/indicators")
async def test_indicators(request: SimpleIndicatorRequest):
    """测试技术指标计算"""
    
    try:
        # 创建模拟K线数据
        kline_data = []
        base_price = 54.0
        
        for i in range(30):
            price = base_price + (i % 10 - 5) * 0.5
            kline_data.append({
                "time": (datetime.now() - timedelta(days=29-i)).strftime('%Y-%m-%d'),
                "open": price - 0.1,
                "high": price + 0.3,
                "low": price - 0.2,
                "close": price,
                "volume": 1000000 + (i % 5) * 100000,
                "turnover": price * 1000000
            })
        
        # 计算技术指标
        config = IndicatorConfig()
        technical_data = TechnicalIndicators.from_kline_data(kline_data, config)
        indicators = technical_data.calculate_all_indicators()
        
        # 简化返回数据，只返回安全的部分
        simplified_indicators = {}
        
        if "trend_indicators" in indicators:
            trend = indicators["trend_indicators"]
            simplified_indicators["trend"] = {}
            
            # MACD - 只返回有效数值
            if "macd" in trend and "current" in trend["macd"]:
                macd_current = trend["macd"]["current"]
                simplified_indicators["trend"]["macd"] = {
                    k: v for k, v in macd_current.items() 
                    if v is not None and isinstance(v, (int, float))
                }
            
            # 移动平均线 - 只返回有效数值
            if "moving_averages" in trend and "current" in trend["moving_averages"]:
                ma_current = trend["moving_averages"]["current"]
                simplified_indicators["trend"]["moving_averages"] = {
                    k: v for k, v in ma_current.items() 
                    if v is not None and isinstance(v, (int, float))
                }
        
        if "momentum_indicators" in indicators:
            momentum = indicators["momentum_indicators"]
            simplified_indicators["momentum"] = {}
            
            # RSI
            if "rsi" in momentum and "current" in momentum["rsi"]:
                rsi_current = momentum["rsi"]["current"]
                if rsi_current is not None and isinstance(rsi_current, (int, float)):
                    simplified_indicators["momentum"]["rsi"] = rsi_current
        
        response = SimpleIndicatorResponse(
            code=request.code,
            period=request.period,
            indicators=simplified_indicators,
            timestamp=datetime.now().isoformat()
        )
        
        return {
            "ret_code": 0,
            "ret_msg": "技术指标计算成功",
            "data": response.model_dump()
        }
        
    except Exception as e:
        return {
            "ret_code": -1,
            "ret_msg": f"计算失败: {str(e)}",
            "data": None
        }

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    print("🚀 启动技术指标测试服务...")
    uvicorn.run(app, host="0.0.0.0", port=8003, reload=True) 