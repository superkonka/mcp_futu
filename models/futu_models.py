from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
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


class StockField(str, Enum):
    """股票字段枚举 - 用于条件选股"""
    # 基本信息
    STOCK_CODE = "STOCK_CODE"                    # 股票代码
    STOCK_NAME = "STOCK_NAME"                    # 股票名称
    CUR_PRICE = "CUR_PRICE"                      # 最新价
    CUR_PRICE_TO_PRE_CLOSE_RATIO = "CUR_PRICE_TO_PRE_CLOSE_RATIO"  # 涨跌幅
    PRICE_CHANGE = "PRICE_CHANGE"                # 涨跌额
    VOLUME = "VOLUME"                            # 成交量
    TURNOVER = "TURNOVER"                        # 成交额
    TURNOVER_RATE = "TURNOVER_RATE"              # 换手率
    AMPLITUDE = "AMPLITUDE"                      # 振幅
    HIGH_PRICE = "HIGH_PRICE"                    # 最高价
    LOW_PRICE = "LOW_PRICE"                      # 最低价
    OPEN_PRICE = "OPEN_PRICE"                    # 开盘价
    PRE_CLOSE_PRICE = "PRE_CLOSE_PRICE"          # 昨收价
    
    # 估值指标
    PE_RATIO = "PE_RATIO"                        # 市盈率
    PB_RATIO = "PB_RATIO"                        # 市净率
    MARKET_VAL = "MARKET_VAL"                    # 总市值
    
    # 技术指标
    MA5 = "MA5"                                  # 5日均线
    MA10 = "MA10"                                # 10日均线
    MA20 = "MA20"                                # 20日均线
    MA30 = "MA30"                                # 30日均线
    MA60 = "MA60"                                # 60日均线
    RSI14 = "RSI14"                              # 14日RSI


class SortDir(str, Enum):
    """排序方向"""
    NONE = "NONE"             # 不排序
    ASCEND = "ASCEND"         # 升序
    DESCEND = "DESCEND"       # 降序


class PlateSetType(str, Enum):
    """板块集合类型"""
    ALL = "ALL"               # 所有板块
    INDUSTRY = "INDUSTRY"     # 行业板块
    REGION = "REGION"         # 地域板块
    CONCEPT = "CONCEPT"       # 概念板块


class PeriodType(str, Enum):
    """周期类型 - 用于资金流向等接口"""
    INTRADAY = "INTRADAY"  # 实时
    DAY = "DAY"           # 日
    WEEK = "WEEK"         # 周
    MONTH = "MONTH"       # 月


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


class CapitalFlowRequest(BaseModel):
    """资金流向请求"""
    code: str = Field(..., description="股票代码，如'HK.00700', 'US.AAPL'")
    period_type: PeriodType = Field(PeriodType.INTRADAY, description="周期类型：INTRADAY(实时), DAY(日), WEEK(周), MONTH(月)")
    start: Optional[str] = Field(None, description="开始日期，格式：'2020-01-01'。为空时自动获取近期数据")
    end: Optional[str] = Field(None, description="结束日期，格式：'2020-12-31'。为空时自动设为当前日期")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class CapitalDistributionRequest(BaseModel):
    """资金分布请求"""
    code: str = Field(..., description="股票代码，如'HK.00700', 'US.AAPL'")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class RehabRequest(BaseModel):
    """复权因子请求"""
    code: str = Field(..., description="股票代码，如'HK.00700', 'US.AAPL'")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class SimpleFilter(BaseModel):
    """简单筛选条件"""
    stock_field: StockField = Field(..., description="筛选字段")
    filter_min: Optional[float] = Field(None, description="区间下限，不传默认为-∞")
    filter_max: Optional[float] = Field(None, description="区间上限，不传默认为+∞")
    is_no_filter: bool = Field(True, description="是否不筛选，True：不筛选，False：筛选")
    sort: SortDir = Field(SortDir.NONE, description="排序方向")


class StockFilterRequest(BaseModel):
    """条件选股请求"""
    market: Market = Field(..., description="市场标识，HK/US/CN")
    filter_list: List[SimpleFilter] = Field(default_factory=list, description="筛选条件列表")
    plate_code: Optional[str] = Field(None, description="板块代码，如'HK.BK1001'")
    begin: int = Field(0, description="数据起始点")
    num: int = Field(50, description="请求数据个数，最多200")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class PlateStockRequest(BaseModel):
    """板块内股票列表请求"""
    plate_code: str = Field(..., description="板块代码，如'HK.BK1001'")
    sort_field: Optional[StockField] = Field(None, description="排序字段")
    sort_dir: SortDir = Field(SortDir.NONE, description="排序方向")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class PlateListRequest(BaseModel):
    """板块列表请求"""
    market: Market = Field(..., description="市场标识，HK/US/CN")
    plate_set_type: PlateSetType = Field(PlateSetType.ALL, description="板块集合类型")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class SubscribeRequest(BaseModel):
    """订阅请求"""
    code_list: List[str] = Field(..., description="股票代码列表")
    subtype_list: List[SubType] = Field(..., description="订阅类型列表")


# 在请求模型区域，紧接着 OrderBookRequest/TickerRequest/RTDataRequest 等相邻处新增 BrokerQueueRequest

class OrderBookRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    num: int = Field(10, description="档位数量")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class TickerRequest(BaseModel):
    """逐笔数据请求"""
    code: str = Field(..., description="股票代码")
    num: int = Field(100, description="数据点数量")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class RTDataRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class BrokerQueueRequest(BaseModel):
    """经纪队列请求"""
    code: str = Field(..., description="股票代码，如'HK.00700'")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class TradingDaysRequest(BaseModel):
    """交易日请求"""
    market: Market = Field(..., description="市场类型")
    start: str = Field(..., description="开始日期，格式：'2020-01-01'")
    end: str = Field(..., description="结束日期，格式：'2020-12-31'")
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


# === MCP专用增强请求模型 ===

class RealtimeQuoteEnhancedRequest(BaseModel):
    """MCP专用：增强实时报价请求"""
    codes: List[str] = Field(..., description="股票代码列表，如['HK.00700', 'US.AAPL']")
    fields: Optional[List[str]] = Field(None, description="指定返回字段，为空则返回核心字段")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class RealtimeOrderBookEnhancedRequest(BaseModel):
    """MCP专用：增强实时摆盘请求"""
    code: str = Field(..., description="股票代码，如'HK.00700'")
    num: int = Field(10, description="档位数量，默认10档")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class RealtimeTickerEnhancedRequest(BaseModel):
    """MCP专用：增强实时逐笔请求"""
    code: str = Field(..., description="股票代码，如'HK.00700'")
    num: int = Field(100, description="获取逐笔条数，默认100条")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class RealtimeDataEnhancedRequest(BaseModel):
    """MCP专用：增强实时分时请求"""
    code: str = Field(..., description="股票代码，如'HK.00700'")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置") 


# === 交易相关枚举和模型 ===

class TrdEnv(str, Enum):
    """交易环境"""
    SIMULATE = "SIMULATE"     # 模拟环境
    REAL = "REAL"            # 真实环境


class Currency(str, Enum):
    """货币类型"""
    NONE = "NONE"           # 无
    HKD = "HKD"             # 港币
    USD = "USD"             # 美元
    CNH = "CNH"             # 离岸人民币
    JPY = "JPY"             # 日元
    SGD = "SGD"             # 新加坡元
    AUD = "AUD"             # 澳元


class TrdMarket(str, Enum):
    """交易市场"""
    HK = "HK"               # 港股
    US = "US"               # 美股
    CN = "CN"               # A股
    HKCC = "HKCC"           # 港股通（沪深）


class PositionSide(str, Enum):
    """持仓方向"""
    LONG = "LONG"           # 长仓（多头）
    SHORT = "SHORT"         # 短仓（空头）
    NONE = "NONE"           # 无


class TrdSide(str, Enum):
    """交易方向"""
    BUY = "BUY"             # 买入
    SELL = "SELL"           # 卖出
    NONE = "NONE"           # 无


class DealStatus(str, Enum):
    """成交状态"""
    OK = "OK"               # 正常
    CANCELLED = "CANCELLED" # 已撤销
    FAILED = "FAILED"       # 失败
    NONE = "NONE"           # 无


# 交易相关请求模型
class AccInfoRequest(BaseModel):
    """查询账户资金请求"""
    trd_env: TrdEnv = Field(TrdEnv.REAL, description="交易环境：SIMULATE(模拟), REAL(真实)")
    acc_id: int = Field(0, description="交易业务账户ID，推荐使用。当传0时以acc_index为准")
    acc_index: int = Field(0, description="交易业务账户列表中的账户序号，默认0表示第1个账户")
    refresh_cache: bool = Field(False, description="是否刷新缓存，True立即请求服务器，False使用OpenD缓存")
    currency: Currency = Field(Currency.HKD, description="计价货币，仅期货账户、综合证券账户适用")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class PositionListRequest(BaseModel):
    """查询持仓请求"""
    code: Optional[str] = Field(None, description="代码过滤，只返回此代码对应的持仓数据。不传则返回所有")
    position_market: Optional[TrdMarket] = Field(None, description="持仓所属市场过滤，默认返回所有市场持仓")
    pl_ratio_min: Optional[float] = Field(None, description="当前盈亏比例下限过滤，仅返回高于此比例的持仓（例如：10表示+10%）")
    pl_ratio_max: Optional[float] = Field(None, description="当前盈亏比例上限过滤，返回低于此比例的持仓（例如：10表示+10%）")
    trd_env: TrdEnv = Field(TrdEnv.SIMULATE, description="交易环境：SIMULATE(模拟), REAL(真实)")
    acc_id: int = Field(0, description="交易业务账户ID，推荐使用。当传0时以acc_index为准")
    acc_index: int = Field(0, description="交易业务账户列表中的账户序号，默认0表示第1个账户")
    refresh_cache: bool = Field(False, description="是否刷新缓存，True立即请求服务器，False使用OpenD缓存")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class HistoryDealListRequest(BaseModel):
    """查询历史成交请求"""
    code: Optional[str] = Field(None, description="代码过滤，只返回此代码对应的成交数据。不传则返回所有")
    deal_market: Optional[TrdMarket] = Field(None, description="成交标的所属市场过滤，默认返回所有市场成交")
    start: Optional[str] = Field(None, description="开始时间，格式：YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH:MM:SS.MS")
    end: Optional[str] = Field(None, description="结束时间，格式：YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH:MM:SS.MS")
    trd_env: TrdEnv = Field(TrdEnv.REAL, description="交易环境：仅支持REAL(真实)，模拟环境暂不支持查询成交数据")
    acc_id: int = Field(0, description="交易业务账户ID，推荐使用。当传0时以acc_index为准")
    acc_index: int = Field(0, description="交易业务账户列表中的账户序号，默认0表示第1个账户")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


class DealListRequest(BaseModel):
    """查询当日成交请求"""
    code: Optional[str] = Field(None, description="代码过滤，只返回此代码对应的成交数据。不传则返回所有")
    deal_market: Optional[TrdMarket] = Field(None, description="成交标的所属市场过滤，默认返回所有市场成交")
    trd_env: TrdEnv = Field(TrdEnv.SIMULATE, description="交易环境：SIMULATE(模拟), REAL(真实)")
    acc_id: int = Field(0, description="交易业务账户ID，推荐使用。当传0时以acc_index为准")
    acc_index: int = Field(0, description="交易业务账户列表中的账户序号，默认0表示第1个账户")
    refresh_cache: bool = Field(False, description="是否刷新缓存，True立即请求服务器，False使用OpenD缓存")
    optimization: DataOptimization = Field(default_factory=DataOptimization, description="数据优化配置")


# 交易相关响应模型
class AccInfoData(BaseModel):
    """账户资金数据"""
    power: Optional[float] = Field(None, description="最大购买力（近似值，按50%融资保证金率计算）")
    max_power_short: Optional[float] = Field(None, description="卖空购买力（近似值，按60%融券保证金率计算）")
    net_cash_power: Optional[float] = Field(None, description="现金购买力（已废弃，请使用分币种字段）")
    total_assets: Optional[float] = Field(None, description="总资产净值（证券+基金+债券资产净值）")
    securities_assets: Optional[float] = Field(None, description="证券资产净值")
    funds_assets: Optional[float] = Field(None, description="基金资产净值")
    bonds_assets: Optional[float] = Field(None, description="债券资产净值")
    cash: Optional[float] = Field(None, description="现金（已废弃，请使用分币种字段）")
    market_val: Optional[float] = Field(None, description="证券市值")
    frozen_cash: Optional[float] = Field(None, description="冻结资金")
    debt_cash: Optional[float] = Field(None, description="欠款金额")
    avl_withdrawal_cash: Optional[float] = Field(None, description="可提现金额")
    currency: Optional[str] = Field(None, description="币种")
    
    # 分币种现金信息
    hkd_cash: Optional[float] = Field(None, description="港币现金")
    hkd_avl_balance: Optional[float] = Field(None, description="港币可用余额")
    hkd_net_cash_power: Optional[float] = Field(None, description="港币现金购买力")
    
    usd_cash: Optional[float] = Field(None, description="美元现金")
    usd_avl_balance: Optional[float] = Field(None, description="美元可用余额")
    usd_net_cash_power: Optional[float] = Field(None, description="美元现金购买力")
    
    cnh_cash: Optional[float] = Field(None, description="离岸人民币现金")
    cnh_avl_balance: Optional[float] = Field(None, description="离岸人民币可用余额")
    cnh_net_cash_power: Optional[float] = Field(None, description="离岸人民币现金购买力")
    
    jpy_cash: Optional[float] = Field(None, description="日元现金")
    jpy_avl_balance: Optional[float] = Field(None, description="日元可用余额")
    jpy_net_cash_power: Optional[float] = Field(None, description="日元现金购买力")
    
    # 期货相关字段
    initial_margin: Optional[float] = Field(None, description="初始保证金")
    maintenance_margin: Optional[float] = Field(None, description="维持保证金")
    long_mv: Optional[float] = Field(None, description="多头市值")
    short_mv: Optional[float] = Field(None, description="空头市值")
    pending_asset: Optional[float] = Field(None, description="待交收资产")
    risk_status: Optional[int] = Field(None, description="风险状态")
    margin_call_margin: Optional[float] = Field(None, description="追加保证金")
    
    # 汇总信息
    account_type: Optional[str] = Field(None, description="账户类型")
    total_cash_value: Optional[float] = Field(None, description="总现金价值")
    available_funds: Optional[float] = Field(None, description="可用资金")
    unrealized_pnl: Optional[float] = Field(None, description="未实现盈亏")


class PositionData(BaseModel):
    """持仓数据"""
    position_id: Optional[str] = Field(None, description="持仓ID")
    position_side: Optional[str] = Field(None, description="持仓方向：LONG(多头), SHORT(空头)")
    code: Optional[str] = Field(None, description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    position_market: Optional[str] = Field(None, description="持仓所属市场")
    qty: Optional[float] = Field(None, description="持有数量")
    can_sell_qty: Optional[float] = Field(None, description="可用数量（可平仓数量）")
    currency: Optional[str] = Field(None, description="交易货币")
    nominal_price: Optional[float] = Field(None, description="市价")
    cost_price: Optional[float] = Field(None, description="摊薄成本价（证券）/平均开仓价（期货）")
    diluted_cost_price: Optional[float] = Field(None, description="摊薄成本价")
    average_cost_price: Optional[float] = Field(None, description="平均成本价")
    
    # 盈亏信息
    market_val: Optional[float] = Field(None, description="市值")
    pl_val: Optional[float] = Field(None, description="盈亏金额")
    pl_ratio: Optional[float] = Field(None, description="盈亏比例")
    average_pl_ratio: Optional[float] = Field(None, description="平均盈亏比例")
    today_pl_val: Optional[float] = Field(None, description="今日盈亏金额")
    today_pl_ratio: Optional[float] = Field(None, description="今日盈亏比例")
    
    # 期货相关
    today_buy_val: Optional[float] = Field(None, description="今日买入成交金额")
    today_buy_qty: Optional[float] = Field(None, description="今日买入成交数量")
    today_sell_val: Optional[float] = Field(None, description="今日卖出成交金额")
    today_sell_qty: Optional[float] = Field(None, description="今日卖出成交数量")
    
    # 状态信息
    break_even_price: Optional[float] = Field(None, description="保本价")
    position_status: Optional[str] = Field(None, description="持仓状态")
    unrealized_pnl: Optional[float] = Field(None, description="未实现盈亏")


class AccInfoResponse(BaseModel):
    """查询账户资金响应"""
    account_info: AccInfoData = Field(..., description="账户资金信息")
    trd_env: str = Field(..., description="交易环境")
    currency: str = Field(..., description="计价货币")
    update_time: str = Field(..., description="数据更新时间")
    data_source: str = Field("futu_api", description="数据来源")
    summary: Dict[str, Any] = Field(default_factory=dict, description="资金摘要信息")


class PositionListResponse(BaseModel):
    """查询持仓列表响应"""
    position_list: List[PositionData] = Field(..., description="持仓列表")
    trd_env: str = Field(..., description="交易环境")
    total_count: int = Field(..., description="持仓总数")
    update_time: str = Field(..., description="数据更新时间")
    data_source: str = Field("futu_api", description="数据来源")
    summary: Dict[str, Any] = Field(default_factory=dict, description="持仓摘要信息")


class DealData(BaseModel):
    """成交数据"""
    deal_id: Optional[str] = Field(None, description="成交号")
    order_id: Optional[str] = Field(None, description="订单号")
    code: Optional[str] = Field(None, description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    trd_side: Optional[str] = Field(None, description="交易方向：BUY(买入), SELL(卖出)")
    deal_market: Optional[str] = Field(None, description="成交标的所属市场")
    qty: Optional[float] = Field(None, description="成交数量")
    price: Optional[float] = Field(None, description="成交价格")
    
    # 时间信息
    create_time: Optional[str] = Field(None, description="创建时间")
    create_timestamp: Optional[float] = Field(None, description="创建时间戳")
    update_timestamp: Optional[float] = Field(None, description="更新时间戳")
    
    # 经纪信息
    counter_broker_id: Optional[int] = Field(None, description="对手经纪号")
    counter_broker_name: Optional[str] = Field(None, description="对手经纪名称")
    
    # 成交金额和费用
    deal_value: Optional[float] = Field(None, description="成交金额")
    currency: Optional[str] = Field(None, description="交易货币")
    status: Optional[str] = Field(None, description="成交状态")
    
    # 期货相关
    deal_fee: Optional[float] = Field(None, description="成交手续费")
    commission: Optional[float] = Field(None, description="佣金")
    stamp_duty: Optional[float] = Field(None, description="印花税")
    clearing_fee: Optional[float] = Field(None, description="结算费")
    
    # 额外信息
    sec_market: Optional[str] = Field(None, description="证券市场")
    deal_type: Optional[str] = Field(None, description="成交类型")


class HistoryDealListResponse(BaseModel):
    """查询历史成交列表响应"""
    deal_list: List[DealData] = Field(..., description="历史成交列表")
    trd_env: str = Field(..., description="交易环境")
    total_count: int = Field(..., description="成交记录总数")
    date_range: str = Field(..., description="查询时间范围")
    update_time: str = Field(..., description="数据更新时间")
    data_source: str = Field("futu_api", description="数据来源")
    summary: Dict[str, Any] = Field(default_factory=dict, description="成交摘要信息")


class DealListResponse(BaseModel):
    """查询当日成交列表响应"""
    deal_list: List[DealData] = Field(..., description="当日成交列表")
    trd_env: str = Field(..., description="交易环境")
    total_count: int = Field(..., description="成交记录总数")
    trade_date: str = Field(..., description="交易日期")
    update_time: str = Field(..., description="数据更新时间")
    data_source: str = Field("futu_api", description="数据来源")
    summary: Dict[str, Any] = Field(default_factory=dict, description="成交摘要信息")


# 在文件末尾添加以下模型

class HistoryOrderListRequest(BaseModel):
    """查询历史订单请求"""
    status_filter_list: Optional[List[str]] = Field(None, description="订单状态过滤列表")
    code: Optional[str] = Field(None, description="代码过滤，只返回此代码对应的订单数据")
    order_market: Optional[TrdMarket] = Field(None, description="订单标的所属市场过滤")
    start: Optional[str] = Field(None, description="开始时间，格式：YYYY-MM-DD HH:MM:SS")
    end: Optional[str] = Field(None, description="结束时间，格式：YYYY-MM-DD HH:MM:SS")
    trd_env: TrdEnv = Field(TrdEnv.REAL, description="交易环境：SIMULATE(模拟), REAL(真实)")
    acc_id: int = Field(0, description="交易业务账户ID，推荐使用。当传0时以acc_index为准")
    acc_index: int = Field(0, description="交易业务账户列表中的账户序号，默认0表示第1个账户")


class OrderFeeQueryRequest(BaseModel):
    """查询订单费用请求"""
    order_id_list: List[str] = Field(..., description="订单号列表")
    trd_env: TrdEnv = Field(TrdEnv.REAL, description="交易环境：SIMULATE(模拟), REAL(真实)")
    acc_id: int = Field(0, description="交易业务账户ID，推荐使用。当传0时以acc_index为准")
    acc_index: int = Field(0, description="交易业务账户列表中的账户序号，默认0表示第1个账户")


class OrderData(BaseModel):
    """订单数据"""
    order_id: Optional[str] = Field(None, description="订单号")
    code: Optional[str] = Field(None, description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    trd_side: Optional[str] = Field(None, description="交易方向：BUY(买入), SELL(卖出)")
    order_type: Optional[str] = Field(None, description="订单类型")
    order_status: Optional[str] = Field(None, description="订单状态")
    order_market: Optional[str] = Field(None, description="订单标的所属市场")
    qty: Optional[float] = Field(None, description="订单数量")
    price: Optional[float] = Field(None, description="订单价格")
    currency: Optional[str] = Field(None, description="交易货币")
    create_time: Optional[str] = Field(None, description="创建时间")
    updated_time: Optional[str] = Field(None, description="最后更新时间")
    dealt_qty: Optional[float] = Field(None, description="成交数量")
    dealt_avg_price: Optional[float] = Field(None, description="成交均价")
    last_err_msg: Optional[str] = Field(None, description="最后的错误描述")
    remark: Optional[str] = Field(None, description="下单时备注的标识")
    time_in_force: Optional[str] = Field(None, description="有效期限")
    fill_outside_rth: Optional[bool] = Field(None, description="是否允许盘前盘后")
    session: Optional[str] = Field(None, description="交易订单时段")
    aux_price: Optional[float] = Field(None, description="触发价格")
    trail_type: Optional[str] = Field(None, description="跟踪类型")
    trail_value: Optional[float] = Field(None, description="跟踪金额/百分比")
    trail_spread: Optional[float] = Field(None, description="指定价差")


class OrderFeeData(BaseModel):
    """订单费用数据"""
    order_id: str = Field(..., description="订单号")
    fee_amount: float = Field(..., description="总费用")
    fee_details: List[tuple] = Field(..., description="收费明细列表，格式：[(费用名称, 费用金额), ...]")


class HistoryOrderListResponse(BaseModel):
    """查询历史订单列表响应"""
    order_list: List[OrderData] = Field(..., description="历史订单列表")
    trd_env: str = Field(..., description="交易环境")
    total_count: int = Field(..., description="订单记录总数")
    date_range: str = Field(..., description="查询时间范围")
    update_time: str = Field(..., description="数据更新时间")
    data_source: str = Field("futu_api", description="数据来源")
    summary: Dict[str, Any] = Field(default_factory=dict, description="订单摘要信息")


class OrderFeeQueryResponse(BaseModel):
    """查询订单费用响应"""
    fee_list: List[OrderFeeData] = Field(..., description="订单费用列表")
    trd_env: str = Field(..., description="交易环境")
    total_count: int = Field(..., description="费用记录总数")
    update_time: str = Field(..., description="数据更新时间")
    data_source: str = Field("futu_api", description="数据来源")
    summary: Dict[str, Any] = Field(default_factory=dict, description="费用摘要信息")