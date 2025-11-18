"""
技术分析指标计算模块
支持常用技术指标的计算和分析
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

try:
    import talib
    TALIB_AVAILABLE = True
    logger.info("TA-Lib 可用，使用优化算法")
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib 不可用，使用纯Python实现")

@dataclass
class IndicatorConfig:
    """指标配置"""
    # MACD参数
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # RSI参数
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    
    # 布林带参数
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    
    # KDJ参数
    kdj_k_period: int = 9
    kdj_d_period: int = 3
    kdj_j_period: int = 3
    
    # 移动平均线参数
    ma_periods: List[int] = None
    
    def __post_init__(self):
        if self.ma_periods is None:
            self.ma_periods = [5, 10, 20, 30, 60, 120, 250]


class TechnicalIndicators:
    """技术分析指标计算器"""
    
    def __init__(self, config: IndicatorConfig = None):
        self.config = config or IndicatorConfig()
    
    @classmethod
    def from_kline_data(cls, kline_data: List[Dict], config: IndicatorConfig = None) -> 'TechnicalData':
        """从K线数据创建技术分析数据"""
        if not kline_data:
            raise ValueError("K线数据不能为空")
        
        # 转换为DataFrame
        df = pd.DataFrame(kline_data)
        
        # 确保数据类型正确
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 按时间排序
        if 'time_key' in df.columns:
            df['time_key'] = pd.to_datetime(df['time_key'])
            df = df.sort_values('time_key').reset_index(drop=True)
        
        return TechnicalData(df, config)
    
    @staticmethod
    def macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """计算MACD指标"""
        # 检查数据量是否足够
        min_required = max(fast, slow, signal) + 10  # 需要额外的数据点用于稳定计算
        if len(prices) < min_required:
            logger.warning(f"MACD计算数据不足：需要至少{min_required}个数据点，实际只有{len(prices)}个")
            # 返回与输入长度相同的NaN数组
            nan_array = np.full(len(prices), np.nan)
            return {
                "macd": nan_array,
                "signal": nan_array,
                "histogram": nan_array
            }
        
        if TALIB_AVAILABLE:
            prices = np.asarray(prices, dtype=np.float64)
            macd_line, signal_line, histogram = talib.MACD(prices, fastperiod=fast, slowperiod=slow, signalperiod=signal)
        else:
            # 纯Python实现
            ema_fast = TechnicalIndicators._ema(prices, fast)
            ema_slow = TechnicalIndicators._ema(prices, slow)
            macd_line = ema_fast - ema_slow
            signal_line = TechnicalIndicators._ema(macd_line, signal)
            histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    @staticmethod
    def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """计算RSI指标"""
        if TALIB_AVAILABLE:
            prices = np.asarray(prices, dtype=np.float64)
            rsi_vals = talib.RSI(prices, timeperiod=period)
            # 平价场景：所有价格相同，设为中性值 50
            if np.nanstd(prices) == 0.0:
                fixed = np.full_like(rsi_vals, np.nan, dtype=np.float64)
                if len(prices) >= period:
                    fixed[period-1:] = 50.0
                return fixed
            return rsi_vals
        else:
            # 纯Python实现
            delta = np.diff(prices)
            gain = np.where(delta > 0, delta, 0.0)
            loss = np.where(delta < 0, -delta, 0.0)
            
            avg_gain = pd.Series(gain).rolling(window=period).mean()
            avg_loss = pd.Series(loss).rolling(window=period).mean()
            
            # 计算RS
            rs = np.where(avg_loss.values != 0.0, avg_gain.values / avg_loss.values, np.nan)
            
            # 平价/边界场景处理：同时为0 -> 50；仅loss为0 -> 100；仅gain为0 -> 0；正常 -> 公式
            both_zero = (avg_gain.values == 0.0) & (avg_loss.values == 0.0)
            only_loss_zero = (avg_loss.values == 0.0) & ~both_zero
            only_gain_zero = (avg_gain.values == 0.0) & ~both_zero
            
            rsi_calc = np.where(
                both_zero, 50.0,
                np.where(
                    only_loss_zero, 100.0,
                    np.where(
                        only_gain_zero, 0.0,
                        100.0 - (100.0 / (1.0 + rs))
                    )
                )
            )
            
            # 对齐长度：在开头插入NaN以匹配原始价格长度
            return np.concatenate([[np.nan], rsi_calc])
    
    @staticmethod
    def bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
        """计算布林带"""
        # 数据验证和预处理
        if len(prices) < period:
            logger.warning(f"布林带计算数据不足：需要至少{period}个数据点，实际只有{len(prices)}个")
            return {
                "upper": np.full(len(prices), np.nan),
                "middle": np.full(len(prices), np.nan),
                "lower": np.full(len(prices), np.nan)
            }
    
        prices = np.asarray(prices, dtype=np.float64)
        if np.any(np.isnan(prices)) or np.any(np.isinf(prices)):
            logger.debug("布林带计算数据包含NaN或无穷大值，将进行清理")
            prices = np.where(np.isinf(prices), np.nan, prices)
    
        logger.debug(f"布林带计算：数据长度={len(prices)}, 周期={period}, 标准差倍数={std_dev}")
        logger.debug(f"价格数据范围：{np.nanmin(prices):.2f} - {np.nanmax(prices):.2f}")
    
        if TALIB_AVAILABLE:
            try:
                upper, middle, lower = talib.BBANDS(
                    prices, timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev
                )
                upper = np.asarray(upper, dtype=np.float64)
                middle = np.asarray(middle, dtype=np.float64)
                lower = np.asarray(lower, dtype=np.float64)
                # 防止 inf
                upper = np.where(np.isinf(upper), np.nan, upper)
                middle = np.where(np.isinf(middle), np.nan, middle)
                lower = np.where(np.isinf(lower), np.nan, lower)
                logger.debug("使用TA-Lib计算布林带成功")
            except Exception as e:
                logger.error(f"TA-Lib布林带计算失败: {e}")
                return {
                    "upper": np.full(len(prices), np.nan),
                    "middle": np.full(len(prices), np.nan),
                    "lower": np.full(len(prices), np.nan)
                }
        else:
            # 纯Python实现 - 增强错误处理
            try:
                df = pd.Series(prices)
                # 将 min_periods 调整为 period，更贴近TA-Lib行为（可选）
                middle_series = df.rolling(window=period, min_periods=period).mean()
                std = df.rolling(window=period, min_periods=period).std()
    
                logger.debug(f"移动平均计算完成，最后值：{middle_series.iloc[-1]:.2f}")
                logger.debug(f"标准差计算完成，最后值：{std.iloc[-1]:.2f}")
    
                # 标准差为0表示窄幅震荡：不再替换为NaN，而是记录为debug
                zero_std_count = int((std == 0).sum())
                if zero_std_count > 0:
                    logger.debug(f"发现{zero_std_count}个标准差为0的点，视为窄幅震荡")
    
                # 填充 NaN 为 0，保证上/下轨可计算（不足窗口长度处保留NaN由 min_periods 控制）
                std = std.fillna(0)
    
                upper_series = middle_series + (std * std_dev)
                lower_series = middle_series - (std * std_dev)
    
                # 统一转换为 numpy 数组，避免后续索引差异
                upper = upper_series.to_numpy()
                middle = middle_series.to_numpy()
                lower = lower_series.to_numpy()
    
                # 确保结果不包含无穷大值
                upper = np.where(np.isinf(upper), np.nan, upper)
                middle = np.where(np.isinf(middle), np.nan, middle)
                lower = np.where(np.isinf(lower), np.nan, lower)
    
                logger.debug("纯Python布林带计算成功")
                # 安全获取最后一个有效值用于日志
                def last_valid(v):
                    for val in reversed(v):
                        if not np.isnan(val):
                            return val
                    return np.nan
                logger.debug(f"布林带最后值 - 上轨：{last_valid(upper):.2f}, 中轨：{last_valid(middle):.2f}, 下轨：{last_valid(lower):.2f}")
    
            except Exception as e:
                logger.error(f"纯Python布林带计算失败: {e}")
                return {
                    "upper": np.full(len(prices), np.nan),
                    "middle": np.full(len(prices), np.nan),
                    "lower": np.full(len(prices), np.nan)
                }
    
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower
        }
    
    @staticmethod
    def kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
            k_period: int = 9, d_period: int = 3, j_period: int = 3) -> Dict[str, np.ndarray]:
        """计算KDJ指标"""
        # 数据验证和预处理
        if len(high) < k_period or len(low) < k_period or len(close) < k_period:
            logger.warning(f"KDJ计算数据不足：需要至少{k_period}个数据点，实际只有{len(close)}个")
            return {
                "k": np.full(len(close), np.nan),
                "d": np.full(len(close), np.nan),
                "j": np.full(len(close), np.nan)
            }
        
        # 检查数据是否包含NaN或无效值
        if (np.any(np.isnan(high)) or np.any(np.isnan(low)) or np.any(np.isnan(close)) or
            np.any(np.isinf(high)) or np.any(np.isinf(low)) or np.any(np.isinf(close))):
            logger.warning("KDJ计算数据包含NaN或无穷大值，将进行清理")
            high = np.where(np.isnan(high) | np.isinf(high), np.nan, high)
            low = np.where(np.isnan(low) | np.isinf(low), np.nan, low)
            close = np.where(np.isnan(close) | np.isinf(close), np.nan, close)
        
        logger.debug(f"KDJ计算：数据长度={len(close)}, K周期={k_period}, D周期={d_period}, J周期={j_period}")
        logger.debug(f"价格范围 - 最高：{np.max(high):.2f}, 最低：{np.min(low):.2f}, 收盘：{close[-1]:.2f}")
        
        if TALIB_AVAILABLE:
            try:
                arr_h = np.asarray(high, dtype=np.float64)
                arr_l = np.asarray(low, dtype=np.float64)
                arr_c = np.asarray(close, dtype=np.float64)
                k_percent, d_percent = talib.STOCH(arr_h, arr_l, arr_c, 
                                                 fastk_period=k_period, 
                                                 slowk_period=d_period, 
                                                 slowd_period=j_period)
                j_percent = 3 * k_percent - 2 * d_percent
                logger.debug("使用TA-Lib计算KDJ成功")
            except Exception as e:
                logger.error(f"TA-Lib KDJ计算失败: {e}")
                return {
                    "k": np.full(len(close), np.nan),
                    "d": np.full(len(close), np.nan),
                    "j": np.full(len(close), np.nan)
                }
        else:
            # 纯Python实现 - 增强错误处理
            try:
                # 使用pandas进行滚动计算，更稳定
                high_series = pd.Series(high)
                low_series = pd.Series(low)
                close_series = pd.Series(close)
                
                # 计算最高价和最低价
                lowest_low = low_series.rolling(window=k_period, min_periods=1).min()
                highest_high = high_series.rolling(window=k_period, min_periods=1).max()
                
                logger.debug(f"滚动计算完成 - 最低价最后值：{lowest_low.iloc[-1]:.2f}, 最高价最后值：{highest_high.iloc[-1]:.2f}")
                
                # 计算价格范围，处理除零情况
                price_range = highest_high - lowest_low
                
                # 处理价格范围为0的情况（所有价格相同）
                zero_range_count = (price_range == 0).sum()
                if zero_range_count > 0:
                    logger.warning(f"发现{zero_range_count}个价格范围为0的点，将设为NaN")
                    price_range = price_range.replace(0, np.nan)
                
                # 计算RSV（未成熟随机值）
                rsv = 100 * (close_series - lowest_low) / price_range
                
                # 处理RSV中的NaN值
                nan_rsv_count = rsv.isna().sum()
                if nan_rsv_count > 0:
                    logger.warning(f"发现{nan_rsv_count}个RSV为NaN的点，将设为50（中性值）")
                    rsv = rsv.fillna(50)  # 当价格范围为0时，RSV设为50（中性值）
                
                logger.debug(f"RSV计算完成，最后值：{rsv.iloc[-1]:.2f}")
                
                # 计算K值（快速随机线）
                k_percent = rsv.ewm(alpha=1/d_period, adjust=False).mean()
                
                # 计算D值（慢速随机线）
                d_percent = k_percent.ewm(alpha=1/j_period, adjust=False).mean()
                
                # 计算J值
                j_percent = 3 * k_percent - 2 * d_percent
                
                # 确保结果在合理范围内（0-100）
                k_percent = np.clip(k_percent, 0, 100)
                d_percent = np.clip(d_percent, 0, 100)
                j_percent = np.clip(j_percent, 0, 100)
                
                logger.debug("纯Python KDJ计算成功")
                logger.debug(f"KDJ最后值 - K：{k_percent.iloc[-1]:.2f}, D：{d_percent.iloc[-1]:.2f}, J：{j_percent.iloc[-1]:.2f}")
                
            except Exception as e:
                logger.error(f"纯Python KDJ计算失败: {e}")
                return {
                    "k": np.full(len(close), np.nan),
                    "d": np.full(len(close), np.nan),
                    "j": np.full(len(close), np.nan)
                }
        
        return {
            "k": k_percent,
            "d": d_percent,
            "j": j_percent
        }
    
    @staticmethod
    def moving_averages(prices: np.ndarray, periods: List[int]) -> Dict[str, np.ndarray]:
        """计算多个周期的移动平均线"""
        mas = {}
        for period in periods:
            if TALIB_AVAILABLE:
                arr = np.asarray(prices, dtype=np.float64)
                mas[f"ma_{period}"] = talib.SMA(arr, timeperiod=period)
            else:
                mas[f"ma_{period}"] = pd.Series(prices).rolling(window=period).mean().values
        return mas
    
    @staticmethod
    def ema(prices: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均线"""
        if TALIB_AVAILABLE:
            prices = np.asarray(prices, dtype=np.float64)
            return talib.EMA(prices, timeperiod=period)
        else:
            return TechnicalIndicators._ema(prices, period)
    
    @staticmethod
    def _ema(prices: np.ndarray, period: int) -> np.ndarray:
        """纯Python实现的EMA"""
        # 检查数据量是否足够
        if len(prices) < period:
            logger.warning(f"EMA计算数据不足：需要至少{period}个数据点，实际只有{len(prices)}个")
            return np.full(len(prices), np.nan)
        
        alpha = 2.0 / (period + 1.0)
        ema = np.full_like(prices, np.nan)
        ema[period-1] = np.mean(prices[:period])
        
        for i in range(period, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """计算平均真实波幅"""
        if TALIB_AVAILABLE:
            high = np.asarray(high, dtype=np.float64)
            low = np.asarray(low, dtype=np.float64)
            close = np.asarray(close, dtype=np.float64)
            return talib.ATR(high, low, close, timeperiod=period)
        else:
            # 计算真实波幅
            prev_close = np.roll(close, 1)
            tr1 = high - low
            tr2 = np.abs(high - prev_close)
            tr3 = np.abs(low - prev_close)
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            tr[0] = tr1[0]  # 第一个值使用high-low
            
            # 计算ATR
            return pd.Series(tr).rolling(window=period).mean().values
    
    @staticmethod
    def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """计算能量潮指标"""
        if TALIB_AVAILABLE:
            return talib.OBV(np.asarray(close, dtype=np.float64), np.asarray(volume, dtype=np.float64))
        else:
            price_change = np.diff(close)
            obv = np.zeros(len(close))
            
            for i in range(1, len(close)):
                if price_change[i-1] > 0:
                    obv[i] = obv[i-1] + volume[i]
                elif price_change[i-1] < 0:
                    obv[i] = obv[i-1] - volume[i]
                else:
                    obv[i] = obv[i-1]
            
            return obv
    
    @staticmethod
    def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """计算成交量加权平均价格"""
        typical_price = (high + low + close) / 3
        cum_volume = np.cumsum(volume)
        cum_price_volume = np.cumsum(typical_price * volume)
        
        # 避免除零
        vwap = np.where(cum_volume != 0, cum_price_volume / cum_volume, typical_price)
        return vwap
    
    @staticmethod
    def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Dict[str, np.ndarray]:
        """计算平均趋向指数"""
        if TALIB_AVAILABLE:
            arr_h = np.asarray(high, dtype=np.float64)
            arr_l = np.asarray(low, dtype=np.float64)
            arr_c = np.asarray(close, dtype=np.float64)
            adx = talib.ADX(arr_h, arr_l, arr_c, timeperiod=period)
            plus_di = talib.PLUS_DI(arr_h, arr_l, arr_c, timeperiod=period)
            minus_di = talib.MINUS_DI(arr_h, arr_l, arr_c, timeperiod=period)
        else:
            # 简化的纯Python实现
            tr = TechnicalIndicators.atr(high, low, close, 1)
            plus_dm = np.maximum(high[1:] - high[:-1], 0)
            minus_dm = np.maximum(low[:-1] - low[1:], 0)
            
            plus_dm = np.concatenate([[0], plus_dm])
            minus_dm = np.concatenate([[0], minus_dm])
            
            tr_mean = pd.Series(tr).rolling(window=period).mean()
            
            # 修复：防止除零错误
            plus_di = np.where(tr_mean != 0, 
                              100 * pd.Series(plus_dm).rolling(window=period).mean() / tr_mean, 
                              0)
            minus_di = np.where(tr_mean != 0, 
                               100 * pd.Series(minus_dm).rolling(window=period).mean() / tr_mean, 
                               0)
            
            # 修复：防止ADX计算中的除零错误
            di_sum = plus_di + minus_di
            dx = np.where(di_sum != 0, 100 * np.abs(plus_di - minus_di) / di_sum, 0)
            adx = pd.Series(dx).rolling(window=period).mean()
        
        return {
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di
        }


class TechnicalData:
    """技术分析数据容器"""
    
    def __init__(self, df: pd.DataFrame, config: IndicatorConfig = None):
        self.df = df.copy()
        self.config = config or IndicatorConfig()
        self._indicators_cache = {}
    
    @property
    def prices(self) -> np.ndarray:
        """收盘价数组"""
        return self.df['close'].values
    
    @property
    def high(self) -> np.ndarray:
        """最高价数组"""
        return self.df['high'].values
    
    @property
    def low(self) -> np.ndarray:
        """最低价数组"""
        return self.df['low'].values
    
    @property
    def open(self) -> np.ndarray:
        """开盘价数组"""
        return self.df['open'].values
    
    @property
    def volume(self) -> np.ndarray:
        """成交量数组"""
        return self.df['volume'].values if 'volume' in self.df.columns else np.ones(len(self.df))
    
    def calculate_all_indicators(self) -> Dict[str, Any]:
        """计算所有技术指标"""
        if 'all_indicators' in self._indicators_cache:
            return self._indicators_cache['all_indicators']
        
        logger.info("开始计算所有技术指标...")
        
        indicators = {
            "trend_indicators": self._calculate_trend_indicators(),
            "momentum_indicators": self._calculate_momentum_indicators(),
            "volatility_indicators": self._calculate_volatility_indicators(),
            "volume_indicators": self._calculate_volume_indicators(),
            "summary": self._generate_summary()
        }
        
        self._indicators_cache['all_indicators'] = indicators
        logger.info("技术指标计算完成")
        return indicators
    
    def _calculate_trend_indicators(self) -> Dict[str, Any]:
        """计算趋势指标"""
        indicators = {}
        
        # MACD
        macd_data = TechnicalIndicators.macd(
            self.prices, 
            self.config.macd_fast, 
            self.config.macd_slow, 
            self.config.macd_signal
        )
        indicators["macd"] = {
            "values": {
                "macd": macd_data["macd"].tolist(),
                "signal": macd_data["signal"].tolist(),
                "histogram": macd_data["histogram"].tolist()
            },
            "current": {
                "macd": float(macd_data["macd"][-1]) if len(macd_data["macd"]) > 0 and not np.isnan(macd_data["macd"][-1]) else None,
                "signal": float(macd_data["signal"][-1]) if len(macd_data["signal"]) > 0 and not np.isnan(macd_data["signal"][-1]) else None,
                "histogram": float(macd_data["histogram"][-1]) if len(macd_data["histogram"]) > 0 and not np.isnan(macd_data["histogram"][-1]) else None
            },
            "signal": self._analyze_macd_signal(macd_data)
        }
        
        # 移动平均线
        ma_data = TechnicalIndicators.moving_averages(self.prices, self.config.ma_periods)
        indicators["moving_averages"] = {
            "values": {k: v.tolist() for k, v in ma_data.items()},
            "current": {k: float(v[-1]) if len(v) > 0 and not np.isnan(v[-1]) else None for k, v in ma_data.items()},
            "signal": self._analyze_ma_signal(ma_data)
        }
        
        # EMA
        ema_12 = TechnicalIndicators.ema(self.prices, 12)
        ema_26 = TechnicalIndicators.ema(self.prices, 26)
        indicators["ema"] = {
            "ema_12": ema_12.tolist(),
            "ema_26": ema_26.tolist(),
            "current_12": float(ema_12[-1]) if len(ema_12) > 0 and not np.isnan(ema_12[-1]) else None,
            "current_26": float(ema_26[-1]) if len(ema_26) > 0 and not np.isnan(ema_26[-1]) else None
        }
        
        # ADX
        try:
            adx_data = TechnicalIndicators.adx(self.high, self.low, self.prices)
            # 安全地处理ADX数据
            adx_current = {}
            for k, v in adx_data.items():
                if hasattr(v, '__len__') and len(v) > 0:
                    # 处理Series或array
                    if hasattr(v, 'iloc'):
                        # pandas Series
                        last_val = v.iloc[-1] if len(v) > 0 else None
                    else:
                        # numpy array
                        last_val = v[-1] if len(v) > 0 else None
                    
                    adx_current[k] = float(last_val) if last_val is not None and not np.isnan(last_val) else None
                else:
                    adx_current[k] = None
            
            indicators["adx"] = {
                "values": {k: (v.tolist() if hasattr(v, 'tolist') else list(v)) for k, v in adx_data.items()},
                "current": adx_current,
                "signal": self._analyze_adx_signal(adx_data)
            }
        except Exception as e:
            logger.warning(f"ADX计算失败: {e}")
            indicators["adx"] = {
                "values": {"adx": [], "plus_di": [], "minus_di": []},
                "current": {"adx": None, "plus_di": None, "minus_di": None},
                "signal": "数据无效"
            }
        
        return indicators
    
    def _calculate_momentum_indicators(self) -> Dict[str, Any]:
        """计算动量指标"""
        indicators = {}
        
        # RSI
        rsi = TechnicalIndicators.rsi(self.prices, self.config.rsi_period)
        indicators["rsi"] = {
            "values": rsi.tolist(),
            "current": float(rsi[-1]) if len(rsi) > 0 and not np.isnan(rsi[-1]) else None,
            "signal": self._analyze_rsi_signal(rsi),
            "overbought_level": self.config.rsi_overbought,
            "oversold_level": self.config.rsi_oversold
        }
        
        # KDJ
        try:
            kdj_data = TechnicalIndicators.kdj(
                self.high, self.low, self.prices,
                self.config.kdj_k_period,
                self.config.kdj_d_period,
                self.config.kdj_j_period
            )
            
            # 简化KDJ数据处理逻辑
            kdj_current = {}
            kdj_values = {}
            
            if kdj_data and all(k in kdj_data for k in ['k', 'd', 'j']):
                for k, v in kdj_data.items():
                    try:
                        # 转换为列表
                        if hasattr(v, 'tolist'):
                            values_list = v.tolist()
                        elif hasattr(v, 'iloc'):
                            values_list = v.tolist()
                        else:
                            values_list = list(v)
                        
                        # 获取最后一个有效值
                        last_val = None
                        for val in reversed(values_list):
                            if val is not None and not np.isnan(val):
                                last_val = float(val)
                                break
                        
                        kdj_current[k] = last_val
                        kdj_values[k] = values_list
                        
                    except Exception as e:
                        logger.warning(f"KDJ {k} 数据处理失败: {e}")
                        kdj_current[k] = None
                        kdj_values[k] = []
            else:
                logger.warning("KDJ数据无效")
                kdj_current = {"k": None, "d": None, "j": None}
                kdj_values = {"k": [], "d": [], "j": []}
            
            indicators["kdj"] = {
                "values": kdj_values,
                "current": kdj_current,
                "signal": self._analyze_kdj_signal(kdj_data) if kdj_data else "数据无效"
            }
        except Exception as e:
            logger.warning(f"KDJ计算失败: {e}")
            indicators["kdj"] = {
                "values": {"k": [], "d": [], "j": []},
                "current": {"k": None, "d": None, "j": None},
                "signal": "数据无效"
            }
        
        return indicators
    
    def _calculate_volatility_indicators(self) -> Dict[str, Any]:
        """计算波动性指标"""
        indicators = {}
        
        # 布林带
        try:
            bb_data = TechnicalIndicators.bollinger_bands(
                self.prices, 
                self.config.bollinger_period, 
                self.config.bollinger_std
            )
            
            # 简化布林带数据处理逻辑
            bb_current = {}
            bb_values = {}
            
            if bb_data and all(k in bb_data for k in ['upper', 'middle', 'lower']):
                for k, v in bb_data.items():
                    try:
                        # 转换为列表
                        if hasattr(v, 'tolist'):
                            values_list = v.tolist()
                        elif hasattr(v, 'iloc'):
                            values_list = v.tolist()
                        else:
                            values_list = list(v)
                        
                        # 获取最后一个有效值
                        last_val = None
                        for val in reversed(values_list):
                            if val is not None and not np.isnan(val):
                                last_val = float(val)
                                break
                        
                        bb_current[k] = last_val
                        bb_values[k] = values_list
                        
                    except Exception as e:
                        logger.warning(f"布林带 {k} 数据处理失败: {e}")
                        bb_current[k] = None
                        bb_values[k] = []
            else:
                logger.warning("布林带数据无效")
                bb_current = {"upper": None, "middle": None, "lower": None}
                bb_values = {"upper": [], "middle": [], "lower": []}
            
            indicators["bollinger_bands"] = {
                "values": bb_values,
                "current": bb_current,
                "signal": self._analyze_bollinger_signal(bb_data) if bb_data else "数据无效",
                "bandwidth": self._calculate_bollinger_bandwidth(bb_data) if bb_data else 0.0
            }
        except Exception as e:
            logger.warning(f"布林带计算失败: {e}")
            indicators["bollinger_bands"] = {
                "values": {"upper": [], "middle": [], "lower": []},
                "current": {"upper": None, "middle": None, "lower": None},
                "signal": "数据无效",
                "bandwidth": 0.0
            }
        
        # ATR
        try:
            atr = TechnicalIndicators.atr(self.high, self.low, self.prices)
            indicators["atr"] = {
                "values": atr.tolist(),
                "current": float(atr[-1]) if len(atr) > 0 and not np.isnan(atr[-1]) else None,
                "average": float(np.nanmean(atr[-20:])) if len(atr) >= 20 else None
            }
        except Exception as e:
            logger.warning(f"ATR计算失败: {e}")
            indicators["atr"] = {
                "values": [],
                "current": None,
                "average": None
            }
        
        return indicators
    
    def _calculate_volume_indicators(self) -> Dict[str, Any]:
        """计算成交量指标"""
        indicators = {}
        
        # OBV
        obv = TechnicalIndicators.obv(self.prices, self.volume)
        
        # 修复：安全的趋势判断
        trend = "平衡"  # 默认值
        if len(obv) >= 5:
            trend = "上涨" if obv[-1] > obv[-5] else "下跌"
        
        indicators["obv"] = {
            "values": obv.tolist(),
            "current": float(obv[-1]),
            "trend": trend
        }
        
        # VWAP
        vwap = TechnicalIndicators.vwap(self.high, self.low, self.prices, self.volume)
        indicators["vwap"] = {
            "values": vwap.tolist(),
            "current": float(vwap[-1]),
            "signal": "看涨" if self.prices[-1] > vwap[-1] else "看跌"
        }
        
        return indicators
    
    def _generate_summary(self) -> Dict[str, str]:
        """生成技术分析总结"""
        # 这里可以根据各种指标生成综合分析
        return {
            "overall_trend": "需要更多数据分析",
            "short_term_signal": "中性",
            "support_level": "待计算",
            "resistance_level": "待计算"
        }
    
    def _analyze_macd_signal(self, macd_data: Dict) -> str:
        """分析MACD信号"""
        macd_array = macd_data["macd"]
        signal_array = macd_data["signal"]
        
        if len(macd_array) < 2 or len(signal_array) < 2:
            return "数据不足"
        
        # 获取最后两个有效值
        try:
            current_macd = macd_array[-1]
            current_signal = signal_array[-1]
            prev_macd = macd_array[-2]
            prev_signal = signal_array[-2]
        except (IndexError, TypeError):
            return "数据不足"
        
        if np.isnan(current_macd) or np.isnan(current_signal):
            return "数据无效"
        
        if np.isnan(prev_macd) or np.isnan(prev_signal):
            # 如果前一个值无效，只看当前状态
            if current_macd > current_signal:
                return "多头_看涨"
            else:
                return "空头_看跌"
        
        # 金叉死叉判断
        if prev_macd <= prev_signal and current_macd > current_signal:
            return "金叉_看涨"
        elif prev_macd >= prev_signal and current_macd < current_signal:
            return "死叉_看跌"
        elif current_macd > current_signal:
            return "多头_看涨"
        else:
            return "空头_看跌"
    
    def _analyze_rsi_signal(self, rsi: np.ndarray) -> str:
        """分析RSI信号"""
        if len(rsi) < 1:
            return "数据不足"
        
        # 确保有有效的最后一个值
        valid_indices = ~np.isnan(rsi)
        if not np.any(valid_indices):
            return "数据无效"
        
        # 获取最后一个有效的RSI值
        valid_rsi_values = rsi[valid_indices]
        if len(valid_rsi_values) == 0:
            return "数据无效"
        
        current_rsi = valid_rsi_values[-1]
        
        if current_rsi >= self.config.rsi_overbought:
            return "超买_看跌"
        elif current_rsi <= self.config.rsi_oversold:
            return "超卖_看涨"
        elif current_rsi > 50:
            return "强势_看涨"
        else:
            return "弱势_看跌"
    
    def _analyze_ma_signal(self, ma_data: Dict) -> str:
        """分析移动平均线信号"""
        if 'ma_5' not in ma_data or 'ma_20' not in ma_data:
            return "数据不足"
        
        ma5_array = ma_data['ma_5']
        ma20_array = ma_data['ma_20']
        
        # 检查数组长度
        if len(ma5_array) == 0 or len(ma20_array) == 0:
            return "数据不足"
        
        # 获取最后有效值
        ma5_valid = ~np.isnan(ma5_array)
        ma20_valid = ~np.isnan(ma20_array)
        
        if not np.any(ma5_valid) or not np.any(ma20_valid):
            return "数据无效"
        
        ma5 = ma5_array[ma5_valid][-1]
        ma20 = ma20_array[ma20_valid][-1]
        current_price = self.prices[-1]
        
        if np.isnan(ma5) or np.isnan(ma20):
            return "数据无效"
        
        if current_price > ma5 > ma20:
            return "多头排列_强烈看涨"
        elif current_price < ma5 < ma20:
            return "空头排列_强烈看跌"
        elif current_price > ma20:
            return "价格在均线上_看涨"
        else:
            return "价格在均线下_看跌"
    
    def _analyze_kdj_signal(self, kdj_data: Dict) -> str:
        """分析KDJ信号"""
        # 安全获取数组
        if not kdj_data or "k" not in kdj_data or "d" not in kdj_data:
            return "数据不足"
        k = kdj_data["k"]
        d = kdj_data["d"]

        # 转为numpy数组，统一为float64
        try:
            if hasattr(k, "to_numpy"):
                k_array = k.to_numpy(dtype=np.float64)
            elif hasattr(k, "values"):
                k_array = np.asarray(k.values, dtype=np.float64)
            else:
                k_array = np.asarray(k, dtype=np.float64)

            if hasattr(d, "to_numpy"):
                d_array = d.to_numpy(dtype=np.float64)
            elif hasattr(d, "values"):
                d_array = np.asarray(d.values, dtype=np.float64)
            else:
                d_array = np.asarray(d, dtype=np.float64)
        except Exception:
            return "数据无效"

        if len(k_array) < 1 or len(d_array) < 1:
            return "数据不足"

        # 获取最后一个有效值
        k_valid = ~np.isnan(k_array)
        d_valid = ~np.isnan(d_array)
        if not np.any(k_valid) or not np.any(d_valid):
            return "数据无效"

        k_current = k_array[k_valid][-1]
        d_current = d_array[d_valid][-1]

        if np.isnan(k_current) or np.isnan(d_current):
            return "数据无效"

        if k_current > 80 and d_current > 80:
            return "超买区_看跌"
        elif k_current < 20 and d_current < 20:
            return "超卖区_看涨"
        elif k_current > d_current:
            return "K大于D_看涨"
        else:
            return "K小于D_看跌"

    def _analyze_bollinger_signal(self, bb_data: Dict) -> str:
        """分析布林带信号"""
        try:
            current_price = float(self.prices[-1])
            upper_array = bb_data["upper"]
            lower_array = bb_data["lower"]
            middle_array = bb_data["middle"]

            if len(upper_array) == 0 or len(lower_array) == 0 or len(middle_array) == 0:
                return "数据不足"

            # 获取最后有效值
            def last_valid(arr):
                vals = arr.tolist() if hasattr(arr, "tolist") else list(arr)
                for v in reversed(vals):
                    if v is not None and not np.isnan(v):
                        return float(v)
                return None

            upper = last_valid(upper_array)
            lower = last_valid(lower_array)
            middle = last_valid(middle_array)

            if upper is None or lower is None or middle is None:
                return "数据无效"
        except (IndexError, TypeError, KeyError, ValueError):
            return "数据不足"

        if np.isnan(upper) or np.isnan(lower) or np.isnan(middle):
            return "数据无效"

        if current_price >= upper:
            return "触及上轨_超买"
        elif current_price <= lower:
            return "触及下轨_超卖"
        elif current_price > middle:
            return "上半区_偏强"
        else:
            return "下半区_偏弱"

    def _calculate_bollinger_bandwidth(self, bb_data: Dict) -> float:
        """计算布林带宽度（健壮版）"""
        upper_arr = bb_data.get("upper")
        lower_arr = bb_data.get("lower")
        middle_arr = bb_data.get("middle")

        # 数组存在性与长度检查
        for arr in (upper_arr, lower_arr, middle_arr):
            if arr is None or len(arr) == 0:
                return 0.0

        # 提取最后一个有效值（非None、非NaN）
        def last_valid(a):
            values = a.tolist() if hasattr(a, "tolist") else list(a)
            for val in reversed(values):
                if val is not None and not np.isnan(val):
                    return float(val)
            return None

        upper = last_valid(upper_arr)
        lower = last_valid(lower_arr)
        middle = last_valid(middle_arr)

        # 若任何轨道无有效值或中轨为0，则返回0避免异常/除零
        if upper is None or lower is None or middle is None:
            return 0.0
        if middle == 0:
            return 0.0

        return (upper - lower) / middle * 100

    def _analyze_adx_signal(self, adx_data: Dict) -> str:
        """分析ADX信号"""
        try:
            adx_array = adx_data["adx"]
            plus_di_array = adx_data["plus_di"]
            minus_di_array = adx_data["minus_di"]

            if len(adx_array) == 0 or len(plus_di_array) == 0 or len(minus_di_array) == 0:
                return "数据不足"

            # 获取最后有效值
            def last_valid(arr):
                vals = arr.tolist() if hasattr(arr, "tolist") else list(arr)
                for v in reversed(vals):
                    if v is not None and not np.isnan(v):
                        return float(v)
                return None

            adx = last_valid(adx_array)
            plus_di = last_valid(plus_di_array)
            minus_di = last_valid(minus_di_array)

            if adx is None or plus_di is None or minus_di is None:
                return "数据无效"
        except (IndexError, TypeError, KeyError, ValueError):
            return "数据不足"

        if np.isnan(adx) or np.isnan(plus_di) or np.isnan(minus_di):
            return "数据无效"

        if adx > 25:
            if plus_di > minus_di:
                return "强趋势_看涨"
            else:
                return "强趋势_看跌"
        else:
            return "无明显趋势_震荡"