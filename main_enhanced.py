#!/usr/bin/env python3
"""
富途MCP服务增强版 - 集成缓存和技术分析功能
支持智能缓存、技术指标计算、形态识别等高级功能
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as log  # Use alias to avoid conflicts
from contextlib import asynccontextmanager
from futu import *
from fastapi_mcp import FastApiMCP

# Ensure we use loguru logger after futu import
logger = log

# 导入原有模块
from services.futu_service import FutuService
from models.futu_models import *
from models.analysis_models import *
from config import settings

# 导入新功能模块  
from cache.cache_manager import DataCacheManager, CacheConfig
from analysis.technical_indicators import TechnicalIndicators, TechnicalData, IndicatorConfig

# 全局变量
futu_service: Optional[FutuService] = None
cache_manager: Optional[DataCacheManager] = None
_server_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global futu_service, cache_manager, _server_ready
    
    logger.info("🚀 启动增强版MCP Futu服务...")
    
    try:
        # 初始化缓存管理器
        cache_config = CacheConfig(
            redis_url="redis://localhost:6379",
            sqlite_path="data/futu_cache.db",
            memory_max_size=2000,
            redis_expire_seconds=7200
        )
        cache_manager = DataCacheManager(cache_config)
        logger.info("✅ 缓存管理器初始化成功")
        
        # 初始化富途服务
        futu_service = FutuService()
        # 设置缓存管理器
        futu_service.cache_manager = cache_manager
        
        # 尝试连接富途OpenD
        if await futu_service.connect():
            logger.info("✅ 富途OpenD连接成功")
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
        
        # 等待 MCP 服务器完全初始化
        logger.info("🔄 等待 MCP 服务器初始化...")
        await asyncio.sleep(3)
        
        _server_ready = True
        logger.info("✅ 增强版 MCP 服务器初始化完成")
            
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        logger.exception("详细错误信息:")
        raise
    finally:
        # 清理资源
        _server_ready = False
        if futu_service:
            await futu_service.disconnect()
        logger.info("🔥 服务已停止")


# 创建FastAPI应用
app = FastAPI(
    title="富途 MCP 增强服务",
    description="集成智能缓存、技术分析、形态识别等功能的专业股票分析平台",
    version="2.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 健康检查 ====================
@app.get("/health")
async def health_check():
    """健康检查"""
    cache_stats = await cache_manager.get_cache_stats() if cache_manager else {}
    
    return {
        "status": "healthy" if _server_ready else "degraded",
        "futu_connected": _server_ready,
        "cache_available": cache_manager is not None,
        "timestamp": datetime.now().isoformat(),
        "cache_stats": cache_stats
    }


# ==================== 时间相关接口 ====================
@app.get("/api/time/current",
         operation_id="get_current_time",
         summary="获取当前时间",
         description="获取服务器当前时间，用于LLM理解时间上下文和模糊时间表达")
async def get_current_time() -> Dict[str, Any]:
    """获取当前时间信息，帮助LLM理解模糊时间表达"""
    now = datetime.now()
    
    # 计算一些常用的时间点
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=now.weekday())  # 本周一
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 股市相关时间（港股为例）
    market_open_today = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_today = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # 判断是否在交易时间
    is_trading_hours = False
    if now.weekday() < 5:  # 周一到周五
        morning_session = (now.replace(hour=9, minute=30) <= now <= now.replace(hour=12, minute=0))
        afternoon_session = (now.replace(hour=13, minute=0) <= now <= now.replace(hour=16, minute=0))
        is_trading_hours = morning_session or afternoon_session
    
    # 生成时间上下文信息
    time_contexts = {
        "今天": today_start.strftime("%Y-%m-%d"),
        "昨天": yesterday_start.strftime("%Y-%m-%d"),
        "本周": week_start.strftime("%Y-%m-%d"),
        "本月": month_start.strftime("%Y-%m-%d"),
        "近期": (now - timedelta(days=7)).strftime("%Y-%m-%d"),  # 最近7天
        "最近": (now - timedelta(days=3)).strftime("%Y-%m-%d"),  # 最近3天
        "这几天": (now - timedelta(days=5)).strftime("%Y-%m-%d"),  # 最近5天
        "上周": (week_start - timedelta(days=7)).strftime("%Y-%m-%d"),
        "上月": (month_start - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d"),
        "最近一个月": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
        "最近三个月": (now - timedelta(days=90)).strftime("%Y-%m-%d")
    }
    
    return {
        "ret_code": 0,
        "ret_msg": "获取当前时间成功",
        "data": {
            # 基础时间信息
            "current_time": now.isoformat(),
            "current_date": now.strftime("%Y-%m-%d"),
            "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": int(now.timestamp()),
            
            # 格式化时间
            "formatted": {
                "iso": now.isoformat(),
                "chinese": now.strftime("%Y年%m月%d日 %H:%M:%S"),
                "date_only": now.strftime("%Y-%m-%d"),
                "time_only": now.strftime("%H:%M:%S"),
                "weekday": now.strftime("%A"),
                "weekday_chinese": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
            },
            
            # 市场时间信息
            "market": {
                "is_trading_day": now.weekday() < 5,
                "is_trading_hours": is_trading_hours,
                "market_open_time": market_open_today.strftime("%H:%M"),
                "market_close_time": market_close_today.strftime("%H:%M"),
                "next_trading_day": _get_next_trading_day(now).strftime("%Y-%m-%d")
            },
            
            # 时间上下文映射（用于模糊时间理解）
            "time_contexts": time_contexts,
            
            # 时间区间建议
            "common_periods": {
                "最近1天": {
                    "start": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近3天": {
                    "start": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近1周": {
                    "start": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近1月": {
                    "start": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "最近3月": {
                    "start": (now - timedelta(days=90)).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                },
                "年初至今": {
                    "start": now.replace(month=1, day=1).strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d")
                }
            },
            
            # LLM提示信息
            "llm_context": {
                "description": "当前服务器时间信息，用于理解用户的模糊时间表达",
                "usage_examples": [
                    "当用户说'最近'时，通常指最近3天",
                    "当用户说'近期'时，通常指最近1周", 
                    "当用户说'这几天'时，通常指最近5天",
                    "股票数据分析建议使用交易日时间范围"
                ]
            }
        }
    }


def _get_next_trading_day(current_time: datetime) -> datetime:
    """计算下一个交易日"""
    next_day = current_time + timedelta(days=1)
    
    # 跳过周末
    while next_day.weekday() >= 5:  # 周六=5, 周日=6
        next_day += timedelta(days=1)
    
    return next_day


# ==================== 原有行情接口（增强版） ====================
@app.post("/api/quote/history_kline",
          operation_id="get_history_kline_enhanced",
          summary="获取历史K线（缓存增强）",
          description="智能缓存的历史K线获取，自动从缓存优化数据获取速度")
async def get_history_kline_enhanced(request: HistoryKLineRequest) -> APIResponse:
    """获取历史K线数据（缓存增强版）"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # 1. 尝试从缓存获取数据
        if cache_manager:
            cached_data = await cache_manager.get_kline_data(
                request.code, request.ktype.value, request.start, request.end
            )
            if cached_data:
                cache_hit = True
                logger.info(f"缓存命中: {request.code} {request.ktype.value}")
                
                execution_time = time.time() - start_time
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"获取历史K线成功（缓存）- 执行时间: {execution_time:.3f}s",
                    data={
                        "kline_data": cached_data,
                        "data_count": len(cached_data),
                        "cache_hit": True,
                        "execution_time": execution_time
                    }
                )
        
        # 2. 从API获取数据
        result = await futu_service.get_history_kline(request)
        
        # 3. 存储到缓存
        if result.ret_code == 0 and cache_manager and result.data.get("kline_data"):
            await cache_manager.store_kline_data(
                request.code, request.ktype.value, 
                request.start, request.end,
                result.data["kline_data"]
            )
        
        execution_time = time.time() - start_time
        
        # 增强返回数据
        if result.ret_code == 0 and result.data:
            result.data.update({
                "cache_hit": cache_hit,
                "execution_time": execution_time,
                "data_source": "futu_api"
            })
            result.ret_msg += f" - 执行时间: {execution_time:.3f}s"
        
        return result
        
    except Exception as e:
        logger.exception(f"获取历史K线失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取历史K线异常: {e}", data=None)


@app.post("/api/quote/stock_quote",
          operation_id="get_stock_quote_enhanced", 
          summary="获取股票报价（缓存增强）")
async def get_stock_quote_enhanced(request: StockQuoteRequest) -> APIResponse:
    """获取股票报价（缓存增强版）"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # 1. 尝试从缓存获取
        if cache_manager:
            cached_data = await cache_manager.get_quote_data(request.code_list)
            if cached_data:
                cache_hit = True
                execution_time = time.time() - start_time
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"获取股票报价成功（缓存）- 执行时间: {execution_time:.3f}s",
                    data={
                        "quotes": cached_data,
                        "data_count": len(cached_data),
                        "cache_hit": True,
                        "execution_time": execution_time
                    }
                )
        
        # 2. 从API获取
        result = await futu_service.get_stock_quote(request)
        
        # 3. 存储到缓存
        if result.ret_code == 0 and cache_manager and result.data.get("quotes"):
            await cache_manager.store_quote_data(request.code_list, result.data["quotes"])
        
        execution_time = time.time() - start_time
        if result.ret_code == 0 and result.data:
            result.data.update({
                "cache_hit": cache_hit,
                "execution_time": execution_time
            })
        
        return result
        
    except Exception as e:
        logger.exception(f"获取股票报价失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票报价异常: {e}", data=None)


# ==================== 技术分析接口 ====================
@app.post("/api/analysis/technical_indicators",
          operation_id="get_technical_indicators",
          summary="获取技术分析指标",
          description="计算MACD、RSI、布林带等技术指标，支持缓存优化")
async def get_technical_indicators(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """获取技术分析指标"""
    start_time = time.time()
    cache_hit = False
    
    logger.info(f"🔍 开始处理技术分析请求: {request.code}, 指标: {request.indicators}")
    
    try:
        # 1. 检查指标缓存
        if cache_manager:
            cached_indicators = await cache_manager.get_indicator_data(
                "comprehensive", request.code, request.dict()
            )
            if cached_indicators:
                cache_hit = True
                execution_time = time.time() - start_time
                
                return {
                    "ret_code": 0,
                    "ret_msg": "技术分析获取成功（缓存）",
                    "data": cached_indicators,
                    "execution_time": execution_time,
                    "cache_hit": True,
                    "data_source": "cache",
                    "timestamp": datetime.now().isoformat()
                }
        
        # 2. 获取K线数据（优先从缓存）
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 根据K线类型智能计算需要的数据量和时间范围
        ktype_multipliers = {
            "K_1M": 1440,     # 1分钟: 1天=1440根K线
            "K_5M": 288,      # 5分钟: 1天=288根K线  
            "K_15M": 96,      # 15分钟: 1天=96根K线
            "K_30M": 48,      # 30分钟: 1天=48根K线
            "K_60M": 24,      # 60分钟: 1天=24根K线
            "K_DAY": 1,       # 日线: 1天=1根K线
            "K_WEEK": 0.2,    # 周线: 1天=0.2根K线
            "K_MON": 0.05     # 月线: 1天=0.05根K线
        }
        
        ktype_str = request.ktype.value if hasattr(request.ktype, 'value') else str(request.ktype)
        multiplier = ktype_multipliers.get(ktype_str, 1)
        
        # 计算需要的最小数据量（考虑技术指标计算需求）
        min_required_points = max(
            request.macd_slow + 10,  # MACD需要慢线周期+额外缓冲
            request.rsi_period + 10,  # RSI需要周期+缓冲
            request.bollinger_period + 10,  # 布林带需要周期+缓冲
            50  # 最少50个数据点
        )
        
        # 根据K线频率计算需要的天数
        if multiplier > 1:  # 分钟线
            days_needed = max(
                int(min_required_points / multiplier) + 15,  # 基于数据点计算+更大缓冲
                30  # 至少30天，对于30分钟线确保足够数据
            )
        else:  # 日线、周线、月线
            days_needed = max(
                int(min_required_points / multiplier) + 20,
                90  # 至少90天
            )
        
        start_date = (datetime.now() - timedelta(days=days_needed)).strftime('%Y-%m-%d')
        max_count = min(1000, int(min_required_points * 2))  # 增加到2倍缓冲并提高上限
        
        logger.info(f"📊 准备获取K线数据: {request.code}, {start_date} ~ {end_date}")
        logger.info(f"📊 K线类型: {ktype_str}, 预计需要: {min_required_points}个数据点, 查询天数: {days_needed}, max_count: {max_count}")
        
        kline_request = HistoryKLineRequest(
            code=request.code,
            start=start_date,
            end=end_date,
            ktype=request.ktype,
            max_count=max_count,
            optimization=request.optimization
        )
        
        logger.info(f"📞 调用K线API...")
        kline_result = await get_history_kline_enhanced(kline_request)
        logger.info(f"📈 K线API返回: {kline_result.ret_code}, {kline_result.ret_msg}")
        
        if kline_result.ret_code != 0:
            return {
                "ret_code": kline_result.ret_code,
                "ret_msg": f"获取K线数据失败: {kline_result.ret_msg}",
                "data": None
            }
        
        kline_data = kline_result.data.get("kline_data", [])
        if not kline_data:
            return {
                "ret_code": -1,
                "ret_msg": "K线数据为空",
                "data": None
            }
        
        # 3. 计算技术指标
        logger.info(f"⚙️  开始计算技术指标，K线数据量: {len(kline_data)}")
        
        config = IndicatorConfig(
            macd_fast=request.macd_fast,
            macd_slow=request.macd_slow,
            macd_signal=request.macd_signal,
            rsi_period=request.rsi_period,
            rsi_overbought=request.rsi_overbought,
            rsi_oversold=request.rsi_oversold,
            bollinger_period=request.bollinger_period,
            bollinger_std=request.bollinger_std,
            ma_periods=request.ma_periods
        )
        
        logger.info("🧮 创建技术分析对象...")
        technical_data = TechnicalIndicators.from_kline_data(kline_data, config)
        logger.info("📈 计算所有指标...")
        indicators = technical_data.calculate_all_indicators()
        logger.info(f"✅ 指标计算完成，包含: {list(indicators.keys())}")
        
        # 4. 构建简化且LLM友好的响应数据
        logger.info("📋 构建简化响应数据...")
        
        # 提取关键指标的当前值和信号，避免过长的历史数据
        simplified_data = _create_simplified_response(indicators, request.code, len(kline_data))
        
        logger.info(f"🔍 简化后数据结构: {list(simplified_data.keys()) if isinstance(simplified_data, dict) else type(simplified_data)}")
        
        response_data = {
            "code": request.code,
            "period": request.period,
            "data_points": len(kline_data),
            "indicators": simplified_data,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("✅ 响应数据构建完成")
        
        # 5. 存储指标到缓存
        if cache_manager:
            await cache_manager.store_indicator_data(
                "comprehensive", request.code, request.model_dump(), response_data
            )
        
        execution_time = time.time() - start_time
        
        # 使用通用的字典响应格式，避免严格的模型验证
        return {
            "ret_code": 0,
            "ret_msg": "技术分析计算完成",
            "data": response_data,
            "execution_time": execution_time,
            "cache_hit": cache_hit,
            "data_source": "calculated",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"技术分析计算失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"技术分析异常: {e}",
            "data": None
        }


def _create_simplified_response(indicators: Dict[str, Any], code: str, data_points: int) -> Dict[str, Any]:
    """创建简化的LLM友好响应格式
    
    只保留关键信息：
    - 当前值 (current)
    - 信号 (signal) 
    - 简要描述
    避免过长的历史数据序列
    """
    
    def extract_current_value(indicator_data):
        """提取指标的当前值"""
        if not isinstance(indicator_data, dict):
            # logger.debug(f"🔍 指标数据不是字典: {type(indicator_data)}")
            return None
            
        current = indicator_data.get("current")
        # logger.debug(f"🔍 当前值原始数据: {current} (类型: {type(current)})")
        
        if isinstance(current, dict):
            # 过滤有效的数值
            valid_current = {k: v for k, v in current.items() 
                           if v is not None and isinstance(v, (int, float)) and not (isinstance(v, float) and (v != v or abs(v) == float('inf')))}
            # logger.debug(f"🔍 过滤后的当前值: {valid_current}")
            return valid_current if valid_current else None
        elif isinstance(current, (int, float)) and not (isinstance(current, float) and (current != current or abs(current) == float('inf'))):
            return current
        return None
    
    def extract_signal(indicator_data):
        """提取指标信号"""
        if isinstance(indicator_data, dict):
            signal = indicator_data.get("signal")
            # logger.debug(f"🔍 信号数据: {signal}")
            return signal
        return None
    
    simplified = {}
    
    # 处理趋势指标 (MACD, MA, EMA等)
    if "trend_indicators" in indicators and indicators["trend_indicators"]:
        # logger.info("🔍 处理趋势指标...")
        trend_data = {}
        trend_indicators = indicators["trend_indicators"]
        
        # MACD
        if "macd" in trend_indicators:
            # logger.info("🔍 处理MACD...")
            macd = trend_indicators["macd"]
            # logger.debug(f"🔍 MACD原始数据: {macd}")
            current_macd = extract_current_value(macd)
            if current_macd:
                trend_data["macd"] = {
                    "current": current_macd,
                    "signal": extract_signal(macd) or "中性",
                    "description": "MACD动量指标"
                }
                # logger.info(f"🔍 MACD处理成功: {trend_data['macd']}")
            # else:
                # logger.warning("🔍 MACD当前值为空")
        
        # 移动平均线
        if "moving_averages" in trend_indicators:
            # logger.info("🔍 处理移动平均线...")
            ma = trend_indicators["moving_averages"]
            # logger.debug(f"🔍 MA原始数据: {ma}")
            current_ma = extract_current_value(ma)
            if current_ma:
                trend_data["moving_averages"] = {
                    "current": current_ma,
                    "signal": extract_signal(ma) or "中性",
                    "description": "移动平均线"
                }
                # logger.info(f"🔍 MA处理成功: {trend_data['moving_averages']}")
            # else:
                # logger.warning("🔍 MA当前值为空")
        
        if trend_data:
            simplified["trend_indicators"] = trend_data
            # logger.info(f"🔍 趋势指标处理完成: {list(trend_data.keys())}")
    
    # 处理动量指标 (RSI, KDJ等)
    if "momentum_indicators" in indicators and indicators["momentum_indicators"]:
        # logger.info("🔍 处理动量指标...")
        momentum_data = {}
        momentum_indicators = indicators["momentum_indicators"]
        
        # RSI
        if "rsi" in momentum_indicators:
            # logger.info("🔍 处理RSI...")
            rsi = momentum_indicators["rsi"]
            # logger.debug(f"🔍 RSI原始数据: {rsi}")
            current_rsi = extract_current_value(rsi)
            if current_rsi:
                momentum_data["rsi"] = {
                    "current": current_rsi,
                    "signal": extract_signal(rsi) or "中性",
                    "description": "相对强弱指标"
                }
                # logger.info(f"🔍 RSI处理成功: {momentum_data['rsi']}")
            # else:
                # logger.warning("🔍 RSI当前值为空")
        
        if momentum_data:
            simplified["momentum_indicators"] = momentum_data
            # logger.info(f"🔍 动量指标处理完成: {list(momentum_data.keys())}")
    
    # 处理技术分析总结
    if "summary" in indicators and indicators["summary"]:
        # logger.info("🔍 处理技术分析总结...")
        summary = indicators["summary"]
        # logger.debug(f"🔍 Summary原始数据: {summary}")
        if isinstance(summary, dict):
            clean_summary = {k: v for k, v in summary.items() if v is not None and v != ""}
            if clean_summary:
                simplified["summary"] = clean_summary
                # logger.info(f"🔍 Summary处理成功: {clean_summary}")
    
    # 如果所有指标都无效，返回基本信息
    if not simplified:
        logger.warning("🔍 所有指标都无效，返回基本信息")
        simplified = {
            "status": "数据计算中，部分指标可能需要更多历史数据",
            "data_points": data_points,
            "note": "技术指标需要足够的历史数据才能计算准确"
        }
    
    logger.info(f"✅ 简化数据包含: {list(simplified.keys())}")
    return simplified


def _clean_indicator_data(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """清理指标数据中的None值，确保Pydantic验证通过"""
    
    def clean_dict_values(data: Dict[str, Any]) -> Dict[str, Any]:
        """递归清理字典中的None值"""
        if not isinstance(data, dict):
            return data
            
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, dict):
                # 递归清理嵌套字典
                cleaned_value = clean_dict_values(value)
                # 只保留包含有效数据的字典
                if cleaned_value:
                    cleaned[key] = cleaned_value
            elif isinstance(value, list):
                # 清理列表，移除None值
                cleaned_list = [v for v in value if v is not None]
                if cleaned_list:
                    cleaned[key] = cleaned_list
            elif value is not None:
                # 保留非None值
                cleaned[key] = value
            # 跳过None值
                
        return cleaned
    
    def clean_indicator_structure(category_data: Dict[str, Any]) -> Dict[str, Any]:
        """清理指标类别数据结构"""
        if not isinstance(category_data, dict):
            return category_data
            
        cleaned_category = {}
        
        for indicator_name, indicator_data in category_data.items():
            if not isinstance(indicator_data, dict):
                # 如果不是字典，直接保留（如signal字符串）
                cleaned_category[indicator_name] = indicator_data
                continue
                
            cleaned_indicator = {}
            
            # 处理values字段
            if "values" in indicator_data:
                values = indicator_data["values"]
                if isinstance(values, dict):
                    cleaned_values = clean_dict_values(values)
                    if cleaned_values:
                        cleaned_indicator["values"] = cleaned_values
                elif isinstance(values, list):
                    cleaned_values = [v for v in values if v is not None]
                    if cleaned_values:
                        cleaned_indicator["values"] = cleaned_values
                elif values is not None:
                    cleaned_indicator["values"] = values
            
            # 处理current字段 - 这是关键字段
            if "current" in indicator_data:
                current = indicator_data["current"]
                if isinstance(current, dict):
                    # 过滤掉None值，只保留有效的float值
                    cleaned_current = {k: v for k, v in current.items() if v is not None and isinstance(v, (int, float))}
                    if cleaned_current:
                        cleaned_indicator["current"] = cleaned_current
                elif current is not None and isinstance(current, (int, float)):
                    cleaned_indicator["current"] = current
                # 如果current全是None或无效，则设为None，这样Pydantic会接受Optional类型
                if "current" not in cleaned_indicator:
                    cleaned_indicator["current"] = None
            
            # 处理其他字段
            for field, value in indicator_data.items():
                if field not in ["values", "current"]:
                    if value is not None:
                        cleaned_indicator[field] = value
            
            # 只有当清理后的指标数据非空时才保留
            if cleaned_indicator:
                cleaned_category[indicator_name] = cleaned_indicator
        
        return cleaned_category
    
    # 清理所有类别的指标数据
    cleaned_indicators = {}
    
    for category, category_data in indicators.items():
        if category == "summary":
            # summary是简单的字符串字典，直接保留
            if isinstance(category_data, dict):
                cleaned_summary = {k: v for k, v in category_data.items() if v is not None}
                if cleaned_summary:
                    cleaned_indicators[category] = cleaned_summary
        else:
            # 清理技术指标数据
            cleaned_category = clean_indicator_structure(category_data)
            if cleaned_category:
                cleaned_indicators[category] = cleaned_category
    
    return cleaned_indicators


@app.post("/api/analysis/macd",
          operation_id="get_macd_indicator",
          summary="获取MACD指标")
async def get_macd_indicator(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """单独获取MACD指标"""
    # 复用comprehensive接口但只返回MACD
    request.indicators = [IndicatorType.MACD]
    return await get_technical_indicators(request)


@app.post("/api/analysis/rsi",
          operation_id="get_rsi_indicator", 
          summary="获取RSI指标")
async def get_rsi_indicator(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """单独获取RSI指标"""
    request.indicators = [IndicatorType.RSI]
    return await get_technical_indicators(request)


# ==================== 缓存管理接口 ====================
@app.get("/api/cache/status",
         operation_id="get_cache_status",
         summary="获取缓存状态")
async def get_cache_status(detailed: bool = False) -> Dict[str, Any]:
    """获取缓存状态"""
    try:
        if not cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        stats = await cache_manager.get_cache_stats()
        
        # 计算使用率
        memory_usage_ratio = stats.get("memory_cache_size", 0) / max(stats.get("memory_max_size", 1), 1)
        
        # 健康状态评估
        health_status = "healthy"
        recommendations = []
        
        if memory_usage_ratio > 0.9:
            health_status = "warning"
            recommendations.append("内存缓存使用率过高，建议清理")
        
        if not stats.get("redis_available", False):
            health_status = "degraded"
            recommendations.append("Redis不可用，建议检查连接")
        
        cache_stats = CacheStats(
            memory_cache_size=stats.get("memory_cache_size", 0),
            memory_max_size=stats.get("memory_max_size", 0),
            memory_usage_ratio=memory_usage_ratio,
            redis_available=stats.get("redis_available", False),
            redis_connected=stats.get("redis_connected"),
            redis_memory_usage=stats.get("redis_memory_usage"),
            sqlite_available=stats.get("sqlite_available", False),
            sqlite_kline_count=stats.get("sqlite_kline_count"),
            sqlite_indicator_count=stats.get("sqlite_indicator_count")
        )
        
        response_data = CacheStatusResponse(
            stats=cache_stats,
            detailed_info=stats if detailed else None,
            health_status=health_status,
            recommendations=recommendations
        )
        
        return {
            "ret_code": 0,
            "ret_msg": "缓存状态获取成功",
            "data": response_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"获取缓存状态失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"获取缓存状态异常: {e}",
            "data": None
        }


@app.post("/api/cache/preload",
          operation_id="preload_cache_data",
          summary="预加载缓存数据")
async def preload_cache_data(request: CachePreloadRequest) -> Dict[str, Any]:
    """预加载缓存数据"""
    start_time = time.time()
    
    try:
        if not cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        # 执行预加载
        await cache_manager.preload_data(request.symbols, request.days)
        
        execution_time = time.time() - start_time
        
        response_data = CacheOperationResponse(
            success=True,
            message=f"成功预加载 {len(request.symbols)} 只股票 {request.days} 天的数据",
            affected_items=len(request.symbols),
            execution_time=execution_time
        )
        
        return {
            "ret_code": 0,
            "ret_msg": "缓存预加载完成",
            "data": response_data,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"缓存预加载失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"缓存预加载异常: {e}",
            "data": None
        }


@app.delete("/api/cache/clear",
           operation_id="clear_cache_data",
           summary="清理缓存数据")
async def clear_cache_data(request: CacheClearRequest) -> Dict[str, Any]:
    """清理缓存数据"""
    start_time = time.time()
    
    try:
        if not cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        # 执行清理
        await cache_manager.clear_cache(request.cache_type.value)
        
        execution_time = time.time() - start_time
        
        response_data = CacheOperationResponse(
            success=True,
            message=f"成功清理 {request.cache_type.value} 缓存",
            execution_time=execution_time
        )
        
        return {
            "ret_code": 0,
            "ret_msg": "缓存清理完成",
            "data": response_data,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"缓存清理失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"缓存清理异常: {e}",
            "data": None
        }


# ==================== 原有接口保持兼容 ====================
@app.post("/api/quote/stock_basicinfo",
          operation_id="get_stock_basicinfo",
          summary="获取股票基本信息",
          description="获取指定市场和证券类型的股票基本信息列表")
async def get_stock_basicinfo(request: StockBasicInfoRequest) -> APIResponse:
    """获取股票基本信息"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_stock_basicinfo(request)
    except Exception as e:
        logger.error(f"获取股票基本信息失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票基本信息失败: {e}", data=None)


@app.post("/api/quote/subscribe", 
          operation_id="subscribe_quotes_deprecated",
          summary="⚠️ 已弃用：订阅功能（MCP不支持）",
          deprecated=True)
async def subscribe_quotes_deprecated(request: SubscribeRequest) -> APIResponse:
    """
    ⚠️ 已弃用：订阅功能不适合MCP协议
    
    MCP是单次同步请求-响应模式，不支持长连接和回调推送。
    
    建议使用以下替代接口：
    - POST /api/quote/stock_quote - 获取实时报价
    - POST /api/quote/order_book - 获取实时摆盘  
    - POST /api/quote/rt_ticker - 获取实时逐笔
    - POST /api/quote/rt_data - 获取实时分时
    - POST /api/quote/current_kline - 获取实时K线
    """
    return APIResponse(
        ret_code=-1, 
        ret_msg="⚠️ 订阅功能已弃用。MCP协议不支持长连接推送。请使用对应的get_*接口直接拉取实时数据。", 
        data={
            "alternative_endpoints": [
                "/api/quote/stock_quote - 获取实时报价",
                "/api/quote/order_book - 获取实时摆盘",
                "/api/quote/rt_ticker - 获取实时逐笔", 
                "/api/quote/rt_data - 获取实时分时",
                "/api/quote/current_kline - 获取实时K线"
            ]
        }
    )


# ==================== MCP专用增强拉取接口 ====================

@app.post("/api/quote/realtime_quote_enhanced",
          operation_id="get_realtime_quote_enhanced",
          summary="🚀 MCP专用：增强实时报价拉取",
          description="专为MCP设计的实时报价接口，支持批量获取，无需订阅，直接拉取最新数据")
async def get_realtime_quote_enhanced(request: RealtimeQuoteEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时报价拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_quote_enhanced(request.codes, request.fields)
    except Exception as e:
        logger.error(f"获取增强实时报价失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时报价失败: {e}", data=None)


@app.post("/api/quote/realtime_orderbook_enhanced",
          operation_id="get_realtime_orderbook_enhanced",
          summary="🚀 MCP专用：增强实时摆盘拉取",
          description="专为MCP设计的实时摆盘接口，无需订阅，直接拉取买卖盘口数据")
async def get_realtime_orderbook_enhanced(request: RealtimeOrderBookEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时摆盘拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_orderbook_enhanced(request.code, request.num)
    except Exception as e:
        logger.error(f"获取增强实时摆盘失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时摆盘失败: {e}", data=None)


@app.post("/api/quote/realtime_ticker_enhanced",
          operation_id="get_realtime_ticker_enhanced",
          summary="🚀 MCP专用：增强实时逐笔拉取",
          description="专为MCP设计的实时逐笔接口，无需订阅，直接拉取最新成交数据")
async def get_realtime_ticker_enhanced(request: RealtimeTickerEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时逐笔拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_ticker_enhanced(request.code, request.num)
    except Exception as e:
        logger.error(f"获取增强实时逐笔失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时逐笔失败: {e}", data=None)


@app.post("/api/quote/realtime_data_enhanced",
          operation_id="get_realtime_data_enhanced",
          summary="🚀 MCP专用：增强实时分时拉取",
          description="专为MCP设计的实时分时接口，无需订阅，直接拉取分时走势数据")
async def get_realtime_data_enhanced(request: RealtimeDataEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时分时拉取"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_realtime_data_enhanced(request.code)
    except Exception as e:
        logger.error(f"获取增强实时分时失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时分时失败: {e}", data=None)


# ==================== 启动配置 ====================

# 创建并配置MCP服务
mcp = FastApiMCP(
    app,
    name="富途证券增强版MCP服务",
    description="增强版富途证券API服务，集成15+技术指标、智能缓存系统、专业量化分析功能。支持港股、美股、A股实时报价，K线数据，技术分析指标计算，智能缓存优化等功能。"
)

# 挂载MCP服务到FastAPI应用
mcp.mount()

if __name__ == "__main__":
    logger.info("🚀 启动富途MCP增强服务...")
    
    uvicorn.run(
        "main_enhanced:app",
        host="0.0.0.0",
        port=8001,  # 使用不同端口避免冲突
        reload=True,
        log_level="info"
    ) 