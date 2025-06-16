from pydantic import BaseModel, Field
from typing import List, Optional, Union
from enum import Enum
from datetime import datetime, date


class Market(str, Enum):
    """市场类型"""
    HK = "HK"  # 港股
    US = "US"  # 美股
    CN = "CN"  # A股
    SG = "SG"  # 新加坡
    JP = "JP"  # 日本


class SecurityType(str, Enum):
    """证券类型"""
    STOCK = "STOCK"        # 股票
    INDEX = "INDEX"        # 指数
    ETF = "ETF"           # ETF
    WARRANT = "WARRANT"    # 窝轮
    BOND = "BOND"         # 债券


class KLType(str, Enum):
    """K线类型"""
    K_1M = "K_1M"         # 1分钟
    K_3M = "K_3M"         # 3分钟
    K_5M = "K_5M"         # 5分钟
    K_15M = "K_15M"       # 15分钟
    K_30M = "K_30M"       # 30分钟
    K_60M = "K_60M"       # 60分钟
    K_DAY = "K_DAY"       # 日K
    K_WEEK = "K_WEEK"     # 周K
    K_MON = "K_MON"       # 月K


class AuType(str, Enum):
    """复权类型"""
    QFQ = "qfq"           # 前复权
    HFQ = "hfq"           # 后复权
    NONE = "None"         # 不复权


class SubType(str, Enum):
    """订阅数据类型"""
    QUOTE = "QUOTE"           # 报价
    ORDER_BOOK = "ORDER_BOOK" # 摆盘
    TICKER = "TICKER"         # 逐笔
    K_1M = "K_1M"            # 1分钟K线
    K_3M = "K_3M"            # 3分钟K线
    K_5M = "K_5M"            # 5分钟K线
    K_15M = "K_15M"          # 15分钟K线
    K_30M = "K_30M"          # 30分钟K线
    K_60M = "K_60M"          # 60分钟K线
    K_DAY = "K_DAY"          # 日K
    K_WEEK = "K_WEEK"        # 周K
    K_MON = "K_MON"          # 月K
    RT_DATA = "RT_DATA"       # 分时数据
    BROKER = "BROKER"         # 经纪队列


class DataOptimization(BaseModel):
    """数据优化配置"""
    enable_optimization: bool = Field(True, description="是否启用数据优化，过滤无意义占位符")
    only_essential_fields: bool = Field(True, description="是否只返回核心字段")
    custom_fields: Optional[List[str]] = Field(None, description="自定义返回字段列表，会覆盖only_essential_fields设置")
    remove_meaningless_values: bool = Field(True, description="是否移除无意义的值（如pe_ratio=0.0）")
    optimize_binary_data: bool = Field(True, description="是否优化二进制数据显示")


# 请求模型
class StockQuoteRequest(BaseModel):
    """股票报价请求"""
    code_list: List[str] = Field(..., description="股票代码列表，如['HK.00700', 'US.AAPL']")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class HistoryKLineRequest(BaseModel):
    """历史K线请求"""
    code: str = Field(..., description="股票代码，如'HK.00700', 'US.AAPL', 'SZ.000001'")
    start: Optional[str] = Field(None, description="开始日期，格式：'2020-01-01'。不填时自动获取最近数据")
    end: Optional[str] = Field(None, description="结束日期，格式：'2020-12-31'。不填时自动设为当前日期")
    ktype: KLType = Field(KLType.K_DAY, description="K线类型：K_1M(1分钟), K_5M(5分钟), K_DAY(日K), K_WEEK(周K), K_MON(月K)等")
    autype: AuType = Field(AuType.QFQ, description="复权类型：qfq(前复权), hfq(后复权), None(不复权)")
    fields: Optional[List[str]] = Field(None, description="返回字段列表，不填则返回所有默认字段")
    max_count: int = Field(100, description="最大数据点数，范围1-1000。未指定时间时，会自动计算时间范围获取最近的N条数据")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class CurrentKLineRequest(BaseModel):
    """当前K线请求"""
    code: str = Field(..., description="股票代码")
    num: int = Field(100, description="数据点数量")
    ktype: KLType = Field(KLType.K_DAY, description="K线类型")
    autype: AuType = Field(AuType.QFQ, description="复权类型")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class MarketSnapshotRequest(BaseModel):
    """市场快照请求"""
    code_list: List[str] = Field(..., description="股票代码列表")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class StockBasicInfoRequest(BaseModel):
    """股票基本信息请求"""
    market: Market = Field(..., description="市场")
    stock_type: SecurityType = Field(SecurityType.STOCK, description="证券类型")
    max_count: Optional[int] = Field(100, description="最大返回数量，默认100只股票，避免token超出")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class SubscribeRequest(BaseModel):
    """订阅请求"""
    code_list: List[str] = Field(..., description="股票代码列表")
    subtype_list: List[SubType] = Field(..., description="订阅类型列表")


class OrderBookRequest(BaseModel):
    """摆盘请求"""
    code: str = Field(..., description="股票代码")
    num: int = Field(10, description="档位数量")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class TickerRequest(BaseModel):
    """逐笔数据请求"""
    code: str = Field(..., description="股票代码")
    num: int = Field(100, description="数据点数量")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class RTDataRequest(BaseModel):
    """分时数据请求"""
    code: str = Field(..., description="股票代码")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class TradingDaysRequest(BaseModel):
    """交易日请求"""
    market: Market = Field(..., description="市场")
    start: Optional[str] = Field(None, description="开始日期")
    end: Optional[str] = Field(None, description="结束日期")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


# 响应模型
class APIResponse(BaseModel):
    """API响应基础模型"""
    ret_code: int = Field(..., description="返回码，0表示成功")
    ret_msg: str = Field(..., description="返回消息")
    data: Optional[dict] = Field(None, description="返回数据")


class StockQuote(BaseModel):
    """股票报价"""
    code: str = Field(..., description="股票代码")
    lot_size: int = Field(..., description="每手股数")
    stock_name: str = Field(..., description="股票名称")
    last_price: float = Field(..., description="最新价")
    open_price: float = Field(..., description="开盘价")
    high_price: float = Field(..., description="最高价")
    low_price: float = Field(..., description="最低价")
    prev_close_price: float = Field(..., description="昨收价")
    volume: int = Field(..., description="成交量")
    turnover: float = Field(..., description="成交额")
    change_rate: float = Field(..., description="涨跌幅")
    update_time: str = Field(..., description="更新时间")


class KLineData(BaseModel):
    """K线数据"""
    code: str = Field(..., description="股票代码")
    time_key: str = Field(..., description="时间")
    open: float = Field(..., description="开盘价")
    close: float = Field(..., description="收盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    volume: int = Field(..., description="成交量")
    turnover: float = Field(..., description="成交额")
    change_rate: float = Field(..., description="涨跌幅")
    last_close: float = Field(..., description="昨收价") 