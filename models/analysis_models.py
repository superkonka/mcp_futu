"""
技术分析相关的数据模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from models.futu_models import DataOptimization


class IndicatorType(str, Enum):
    """技术指标类型"""
    MACD = "macd"
    RSI = "rsi"
    BOLLINGER = "bollinger_bands"
    KDJ = "kdj"
    MA = "moving_averages"
    EMA = "ema"
    ADX = "adx"
    ATR = "atr"
    OBV = "obv"
    VWAP = "vwap"
    ALL = "all"


class CacheType(str, Enum):
    """缓存类型"""
    MEMORY = "memory"
    REDIS = "redis"
    SQLITE = "sqlite"
    ALL = "all"


class TechnicalAnalysisRequest(BaseModel):
    """技术分析请求"""
    code: str = Field(..., description="股票代码")
    indicators: List[IndicatorType] = Field(default=[IndicatorType.ALL], description="要计算的指标类型")
    period: int = Field(50, description="分析周期（天数）")
    ktype: str = Field("K_DAY", description="K线类型")
    
    # 指标参数
    macd_fast: int = Field(12, description="MACD快线周期")
    macd_slow: int = Field(26, description="MACD慢线周期")
    macd_signal: int = Field(9, description="MACD信号线周期")
    
    rsi_period: int = Field(14, description="RSI计算周期")
    rsi_overbought: float = Field(70, description="RSI超买阈值")
    rsi_oversold: float = Field(30, description="RSI超卖阈值")
    
    bollinger_period: int = Field(20, description="布林带周期")
    bollinger_std: float = Field(2.0, description="布林带标准差倍数")
    
    ma_periods: List[int] = Field([5, 10, 20, 30, 60], description="移动平均线周期")
    
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class PatternRequest(BaseModel):
    """K线形态识别请求"""
    code: str = Field(..., description="股票代码")
    period: int = Field(30, description="分析周期（天数）")
    ktype: str = Field("K_DAY", description="K线类型")
    patterns: List[str] = Field(default=[], description="指定要识别的形态，为空则识别所有")


class SupportResistanceRequest(BaseModel):
    """支撑阻力位分析请求"""
    code: str = Field(..., description="股票代码")
    period: int = Field(60, description="分析周期（天数）")
    ktype: str = Field("K_DAY", description="K线类型")
    levels_count: int = Field(5, description="返回的支撑阻力位数量")


class CacheStatusRequest(BaseModel):
    """缓存状态请求"""
    detailed: bool = Field(False, description="是否返回详细信息")


class CachePreloadRequest(BaseModel):
    """缓存预加载请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    days: int = Field(30, description="预加载天数")
    ktypes: List[str] = Field(["K_DAY"], description="K线类型列表")


class CacheClearRequest(BaseModel):
    """缓存清理请求"""
    cache_type: CacheType = Field(default=CacheType.ALL, description="要清理的缓存类型")
    symbols: Optional[List[str]] = Field(default=None, description="指定股票代码，为空则清理所有")


# 响应模型
class TechnicalIndicatorData(BaseModel):
    """技术指标数据"""
    values: Optional[Union[List[float], Dict[str, Any]]] = Field(None, description="指标数值序列")
    current: Optional[Union[float, Dict[str, Any]]] = Field(None, description="当前值") 
    signal: Optional[str] = Field(None, description="技术信号")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="额外信息")


class TechnicalAnalysisResponse(BaseModel):
    """技术分析响应"""
    code: str = Field(..., description="股票代码")
    period: int = Field(..., description="分析周期")
    data_points: int = Field(..., description="数据点数量")
    
    trend_indicators: Optional[Dict[str, TechnicalIndicatorData]] = Field(None, description="趋势指标")
    momentum_indicators: Optional[Dict[str, TechnicalIndicatorData]] = Field(None, description="动量指标")
    volatility_indicators: Optional[Dict[str, TechnicalIndicatorData]] = Field(None, description="波动性指标")
    volume_indicators: Optional[Dict[str, TechnicalIndicatorData]] = Field(None, description="成交量指标")
    
    summary: Optional[Dict[str, str]] = Field(None, description="技术分析总结")
    timestamp: str = Field(..., description="分析时间戳")


class PatternResult(BaseModel):
    """K线形态识别结果"""
    pattern_name: str = Field(..., description="形态名称")
    confidence: float = Field(..., description="置信度(0-1)")
    signal: str = Field(..., description="信号类型：看涨/看跌/中性")
    description: str = Field(..., description="形态描述")
    start_date: str = Field(..., description="形态开始日期")
    end_date: str = Field(..., description="形态结束日期")


class PatternResponse(BaseModel):
    """K线形态识别响应"""
    code: str = Field(..., description="股票代码")
    period: int = Field(..., description="分析周期")
    patterns: List[PatternResult] = Field(..., description="识别到的形态")
    overall_signal: str = Field(..., description="综合信号")
    timestamp: str = Field(..., description="分析时间戳")


class SupportResistanceLevel(BaseModel):
    """支撑阻力位"""
    level: float = Field(..., description="价格水平")
    type: str = Field(..., description="类型：支撑/阻力")
    strength: float = Field(..., description="强度(0-1)")
    touches: int = Field(..., description="触及次数")
    last_touch_date: str = Field(..., description="最后触及日期")


class SupportResistanceResponse(BaseModel):
    """支撑阻力位分析响应"""
    code: str = Field(..., description="股票代码")
    current_price: float = Field(..., description="当前价格")
    levels: List[SupportResistanceLevel] = Field(..., description="支撑阻力位")
    nearest_support: Optional[float] = Field(None, description="最近支撑位")
    nearest_resistance: Optional[float] = Field(None, description="最近阻力位")
    timestamp: str = Field(..., description="分析时间戳")


class CacheStats(BaseModel):
    """缓存统计信息"""
    memory_cache_size: int = Field(..., description="内存缓存条目数")
    memory_max_size: int = Field(..., description="内存缓存最大容量")
    memory_usage_ratio: float = Field(..., description="内存使用率")
    
    redis_available: bool = Field(..., description="Redis是否可用")
    redis_connected: Optional[bool] = Field(None, description="Redis连接状态")
    redis_memory_usage: Optional[str] = Field(None, description="Redis内存使用量")
    
    sqlite_available: bool = Field(..., description="SQLite是否可用")
    sqlite_kline_count: Optional[int] = Field(None, description="SQLite K线缓存数量")
    sqlite_indicator_count: Optional[int] = Field(None, description="SQLite指标缓存数量")
    
    total_hit_rate: Optional[float] = Field(None, description="总体缓存命中率")


class CacheStatusResponse(BaseModel):
    """缓存状态响应"""
    stats: CacheStats = Field(..., description="缓存统计")
    detailed_info: Optional[Dict[str, Any]] = Field(None, description="详细信息")
    health_status: str = Field(..., description="健康状态")
    recommendations: List[str] = Field(default=[], description="优化建议")


class CacheOperationResponse(BaseModel):
    """缓存操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")
    affected_items: Optional[int] = Field(None, description="影响的条目数")
    execution_time: Optional[float] = Field(None, description="执行时间（秒）")


# 增强的API响应
class EnhancedAPIResponse(BaseModel):
    """增强的API响应"""
    ret_code: int = Field(..., description="返回码，0表示成功")
    ret_msg: str = Field(..., description="返回消息")
    data: Optional[Union[
        TechnicalAnalysisResponse,
        PatternResponse, 
        SupportResistanceResponse,
        CacheStatusResponse,
        CacheOperationResponse,
        Dict[str, Any]
    ]] = Field(None, description="返回数据")
    
    # 元数据
    execution_time: Optional[float] = Field(None, description="执行时间（秒）")
    cache_hit: Optional[bool] = Field(None, description="是否命中缓存")
    data_source: Optional[str] = Field(None, description="数据来源")
    timestamp: Optional[str] = Field(None, description="响应时间戳")


# 实时数据相关模型
class AlertRule(BaseModel):
    """预警规则"""
    rule_id: str = Field(..., description="规则ID")
    code: str = Field(..., description="股票代码")
    indicator: str = Field(..., description="指标名称")
    condition: str = Field(..., description="条件：gt/lt/eq/cross_above/cross_below")
    threshold: float = Field(..., description="阈值")
    enabled: bool = Field(True, description="是否启用")


class AlertRequest(BaseModel):
    """创建预警请求"""
    rules: List[AlertRule] = Field(..., description="预警规则列表")
    notification_methods: List[str] = Field(default=["log"], description="通知方式")


class SignalScanRequest(BaseModel):
    """信号扫描请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    signal_types: List[str] = Field(default=["golden_cross", "rsi_oversold", "bollinger_squeeze"], description="信号类型")
    min_confidence: float = Field(0.7, description="最小置信度")


class TradingSignal(BaseModel):
    """交易信号"""
    code: str = Field(..., description="股票代码")
    signal_type: str = Field(..., description="信号类型")
    direction: str = Field(..., description="方向：买入/卖出")
    confidence: float = Field(..., description="置信度")
    price: float = Field(..., description="信号价格")
    indicator_values: Dict[str, float] = Field(..., description="相关指标值")
    description: str = Field(..., description="信号描述")
    timestamp: str = Field(..., description="信号时间")