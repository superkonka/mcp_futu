import numpy as np
import talib
from typing import Dict, List, Any, Union
from loguru import logger
from app.models.analysis import IndicatorType

class TechnicalAnalysisService:
    """技术分析服务"""
    
    @staticmethod
    def calculate(prices: List[float], indicators: List[str], params: Dict[str, Any] = None) -> Dict[str, Any]:
        """计算技术指标"""
        if not prices or len(prices) < 2:
            return {}
            
        # 转换为numpy数组，必须是float64类型
        close_prices = np.array(prices, dtype=np.float64)
        result = {}
        params = params or {}
        
        for ind in indicators:
            try:
                if ind == IndicatorType.MACD or ind == "macd":
                    # MACD默认参数: 12, 26, 9
                    p = params.get("macd", {})
                    fast = p.get("fast", 12)
                    slow = p.get("slow", 26)
                    signal = p.get("signal", 9)
                    
                    macd, macdsignal, macdhist = talib.MACD(
                        close_prices, fastperiod=fast, slowperiod=slow, signalperiod=signal
                    )
                    # 取最后一个有效值
                    result["macd"] = {
                        "dif": float(macd[-1]) if not np.isnan(macd[-1]) else None,
                        "dea": float(macdsignal[-1]) if not np.isnan(macdsignal[-1]) else None,
                        "macd": float(macdhist[-1]) * 2 if not np.isnan(macdhist[-1]) else None # 富途MACD通常是hist * 2
                    }
                    
                elif ind == IndicatorType.RSI or ind == "rsi":
                    # RSI默认参数: 14
                    p = params.get("rsi", {})
                    period = p.get("period", 14)
                    
                    real = talib.RSI(close_prices, timeperiod=period)
                    result["rsi"] = float(real[-1]) if not np.isnan(real[-1]) else None
                    
                elif ind == IndicatorType.BOLL or ind == "bollinger_bands":
                    # BOLL默认参数: 20, 2, 2, 0
                    p = params.get("bollinger_bands", {})
                    period = p.get("period", 20)
                    nbdevup = p.get("nbdevup", 2)
                    nbdevdn = p.get("nbdevdn", 2)
                    
                    upper, middle, lower = talib.BBANDS(
                        close_prices, timeperiod=period, nbdevup=nbdevup, nbdevdn=nbdevdn, matype=0
                    )
                    result["bollinger_bands"] = {
                        "upper": float(upper[-1]) if not np.isnan(upper[-1]) else None,
                        "middle": float(middle[-1]) if not np.isnan(middle[-1]) else None,
                        "lower": float(lower[-1]) if not np.isnan(lower[-1]) else None
                    }
                
                elif ind == IndicatorType.MA or ind == "moving_averages":
                    # MA默认参数: [5, 10, 20, 30, 60]
                    p = params.get("moving_averages", {})
                    periods = p.get("periods", [5, 10, 20, 30, 60])
                    
                    ma_result = {}
                    for period in periods:
                        real = talib.MA(close_prices, timeperiod=period, matype=0)
                        ma_result[f"ma{period}"] = float(real[-1]) if not np.isnan(real[-1]) else None
                    result["moving_averages"] = ma_result

                elif ind == IndicatorType.KDJ or ind == "kdj":
                     # TALib没有直接的KDJ，需要用STOCH计算
                     # STOCH返回slowk, slowd
                     # KDJ一般参数: 9, 3, 3
                     p = params.get("kdj", {})
                     fastk_period = p.get("fastk_period", 9)
                     slowk_period = p.get("slowk_period", 3)
                     slowd_period = p.get("slowd_period", 3)
                     
                     # 注意：STOCH需要high, low, close，这里简化只有close可能不准
                     # 如果只有close，只能近似计算或者跳过
                     # 为了准确性，我们假设调用者会传入high/low，但这里接口只收了prices(close)
                     # 这是一个限制，后续应该扩展接口接收完整K线数据
                     pass

            except Exception as e:
                logger.error(f"计算指标 {ind} 失败: {e}")
                result[ind] = None
                
        return result

    @staticmethod
    def analyze_signal(indicators: Dict[str, Any]) -> Dict[str, str]:
        """根据指标生成简单信号"""
        signals = {}
        
        # RSI信号
        rsi = indicators.get("rsi")
        if rsi is not None:
            if rsi > 70:
                signals["rsi"] = "OVERBOUGHT" # 超买
            elif rsi < 30:
                signals["rsi"] = "OVERSOLD" # 超卖
            else:
                signals["rsi"] = "NEUTRAL"
                
        # MACD信号
        macd = indicators.get("macd")
        if macd:
            dif = macd.get("dif")
            dea = macd.get("dea")
            hist = macd.get("macd")
            if dif is not None and dea is not None:
                if dif > dea and hist > 0:
                    signals["macd"] = "BULLISH" # 金叉/多头
                elif dif < dea and hist < 0:
                    signals["macd"] = "BEARISH" # 死叉/空头
                    
        return signals

analysis_service = TechnicalAnalysisService()
