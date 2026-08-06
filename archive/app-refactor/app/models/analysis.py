from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum

class IndicatorType(str, Enum):
    """技术指标类型"""
    MACD = "macd"
    RSI = "rsi"
    KDJ = "kdj"
    BOLL = "bollinger_bands"
    MA = "moving_averages"
    EMA = "ema"
    VOL = "volume"

class TechnicalAnalysisRequest(BaseModel):
    """技术分析请求"""
    code: str = Field(..., description="股票代码")
    indicators: List[Union[IndicatorType, str]] = Field(..., description="指标列表")
    ktype: str = Field("K_DAY", description="K线类型")
    period: int = Field(100, description="计算周期数据点数")
    params: Optional[Dict[str, Any]] = Field(None, description="指标参数，如 {'macd': {'fast': 12, 'slow': 26, 'signal': 9}}")

class TechnicalAnalysisResponse(BaseModel):
    """技术分析响应"""
    code: str
    timestamp: float
    indicators: Dict[str, Any]
    signals: Dict[str, str] = Field(default_factory=dict, description="交易信号")
