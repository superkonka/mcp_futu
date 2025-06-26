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
_mcp_initialized = False  # 新增MCP初始化状态标志


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global futu_service, cache_manager, _server_ready, _mcp_initialized
    
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
        
        # 等待服务完全初始化
        await asyncio.sleep(3)
        
        # 创建并配置MCP服务 - 移到这里，确保在服务初始化后
        mcp = FastApiMCP(
            app,
            name="富途证券增强版MCP服务",
            description="增强版富途证券API服务，集成15+技术指标、智能缓存系统、专业量化分析功能。支持港股、美股、A股实时报价，K线数据，技术分析指标计算，智能缓存优化，交易历史查询等功能。注意：持仓历史需通过历史成交数据计算。"
        )
        
        # 挂载MCP服务到FastAPI应用
        mcp.mount()
        
        # 增加额外的等待时间确保MCP完全初始化
        logger.info("🔄 等待 MCP 服务器完全初始化...")
        await asyncio.sleep(8)  # 增加等待时间到8秒
        
        _server_ready = True
        _mcp_initialized = True
        logger.info("✅ 增强版 MCP 服务器初始化完成")
            
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        logger.exception("详细错误信息:")
        raise
    finally:
        # 清理资源
        _server_ready = False
        _mcp_initialized = False
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


# ==================== 启动事件处理 ====================
@app.on_event("startup")
async def startup_event():
    """应用启动事件 - 确保MCP完全初始化"""
    global _server_ready, _mcp_initialized
    
    # 等待额外的初始化时间
    await asyncio.sleep(2)
    
    if not _server_ready:
        logger.warning("⚠️  服务器初始化延迟，请稍后重试连接")
    elif not _mcp_initialized:
        logger.warning("⚠️  MCP服务初始化延迟，请稍后重试连接")
    else:
        logger.info("✅ 服务器和MCP服务都已就绪")


# ==================== 健康检查 ====================
@app.get("/health")
async def health_check():
    """健康检查"""
    cache_stats = await cache_manager.get_cache_stats() if cache_manager else {}
    
    return {
        "status": "healthy" if _server_ready else "degraded",
        "futu_connected": _server_ready,
        "cache_available": cache_manager is not None,
        "mcp_ready": _mcp_initialized,  # 新增MCP状态
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
@app.post("/api/system/request_quote_rights",
          operation_id="request_quote_rights", 
          summary="🔧 请求最高行情权限",
          description="手动请求最高行情权限，解决权限被抢占的问题")
async def request_quote_rights() -> Dict[str, Any]:
    """手动请求最高行情权限"""
    if not _server_ready or not futu_service:
        return {
            "success": False,
            "message": "服务未就绪",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # 强制检查并请求权限
        logger.info("📞 接收到手动权限请求...")
        success = await futu_service._check_and_ensure_quote_rights(force_check=True)
        
        return {
            "success": success,
            "message": "权限请求成功" if success else "权限请求失败，请检查OpenD连接和Telnet端口",
            "rights_checked": futu_service._quote_rights_checked,
            "last_check_time": futu_service._last_quote_rights_check,
            "auto_request_enabled": futu_service._quote_rights_auto_request,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"手动权限请求异常: {str(e)}")
        return {
            "success": False,
            "message": f"权限请求异常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


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


@app.post("/api/quote/trading_days", 
          operation_id="get_trading_days",
          summary="获取交易日",
          description="获取指定市场在指定时间段内的交易日列表")
async def get_trading_days(request: TradingDaysRequest) -> APIResponse:
    """获取交易日 - 查询指定时间段内的交易日"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_trading_days(request)
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取交易日历失败: {e}", data=None)


@app.post("/api/quote/capital_flow", 
          operation_id="get_capital_flow",
          summary="获取资金流向",
          description="获取个股资金流向数据，包括主力、大单、中单、小单的净流入情况")
async def get_capital_flow(request: CapitalFlowRequest) -> APIResponse:
    """获取资金流向 - 分析主力资金动向和散户情绪"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_capital_flow(request)
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取资金流向失败: {e}", data=None)


@app.post("/api/quote/capital_distribution", 
          operation_id="get_capital_distribution",
          summary="获取资金分布",
          description="获取个股当前资金分布情况，分析特大单、大单、中单、小单的流入流出对比")
async def get_capital_distribution(request: CapitalDistributionRequest) -> APIResponse:
    """获取资金分布"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_capital_distribution(request)
    except Exception as e:
        logger.error(f"获取资金分布异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取资金分布异常: {str(e)}")


@app.post("/api/quote/rehab", 
          operation_id="get_rehab",
          summary="获取复权因子",
          description="获取股票复权因子数据，包括拆股、合股、送股、转增股、配股、增发等公司行为的复权信息")
async def get_rehab(request: RehabRequest) -> APIResponse:
    """获取复权因子"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_rehab(request)
    except Exception as e:
        logger.error(f"获取复权因子异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取复权因子异常: {str(e)}")


@app.post("/api/market/stock_filter", 
          operation_id="get_stock_filter",
          summary="条件选股",
          description="基于多种条件筛选股票，支持价格、成交量、技术指标等多维度筛选，支持板块过滤")
async def get_stock_filter(request: StockFilterRequest) -> APIResponse:
    """条件选股"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_stock_filter(request)
    except Exception as e:
        logger.error(f"条件选股异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"条件选股异常: {str(e)}")


@app.post("/api/market/plate_stock", 
          operation_id="get_plate_stock",
          summary="获取板块内股票列表",
          description="获取指定板块内的所有股票列表，支持按字段排序")
async def get_plate_stock(request: PlateStockRequest) -> APIResponse:
    """获取板块内股票列表"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_plate_stock(request)
    except Exception as e:
        logger.error(f"获取板块内股票列表异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取板块内股票列表异常: {str(e)}")


@app.post("/api/market/plate_list", 
          operation_id="get_plate_list",
          summary="获取板块列表",
          description="获取指定市场的板块列表，支持按板块类型过滤（行业、概念、地域板块）")
async def get_plate_list(request: PlateListRequest) -> APIResponse:
    """获取板块列表"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_plate_list(request)
    except Exception as e:
        logger.error(f"获取板块列表异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取板块列表异常: {str(e)}")


# ==================== 交易相关接口 ====================

@app.post("/api/trade/acc_info",
          operation_id="get_acc_info", 
          summary="查询账户资金",
          description="查询交易业务账户的资产净值、证券市值、现金、购买力等资金数据")
async def get_acc_info(request: AccInfoRequest) -> APIResponse:
    """查询账户资金 - 获取账户总资产、现金、购买力等资金信息"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_acc_info(request)
    except Exception as e:
        logger.error(f"查询账户资金异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        
        raise HTTPException(status_code=500, detail=f"查询账户资金失败: {error_msg}")


@app.post("/api/trade/position_list",
          operation_id="get_position_list",
          summary="查询持仓列表", 
          description="查询交易业务账户的持仓列表，支持代码过滤、市场过滤、盈亏比例过滤等多种筛选条件")
async def get_position_list(request: PositionListRequest) -> APIResponse:
    """查询持仓列表 - 获取账户所有持仓信息，包含盈亏分析和市场分布"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_position_list(request)
    except Exception as e:
        logger.error(f"查询持仓列表异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        elif "持仓" in error_msg:
            error_msg = "持仓数据获取失败，请检查账户是否有持仓或网络连接"
        
        raise HTTPException(status_code=500, detail=f"查询持仓列表失败: {error_msg}")


@app.post("/api/trade/history_deal_list",
          operation_id="get_history_deal_list",
          summary="查询历史成交", 
          description="查询交易业务账户的历史成交列表，支持代码过滤、市场过滤、时间范围过滤。注意：仅支持真实环境")
async def get_history_deal_list(request: HistoryDealListRequest) -> APIResponse:
    """查询历史成交 - 获取账户历史成交记录，包含买卖分析和费用统计"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_history_deal_list(request)
    except Exception as e:
        logger.error(f"查询历史成交异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        elif "历史成交" in error_msg or "成交" in error_msg:
            error_msg = "历史成交数据获取失败，请检查时间范围或账户权限"
        elif "模拟" in error_msg:
            error_msg = "历史成交查询仅支持真实环境，不支持模拟环境"
        
        raise HTTPException(status_code=500, detail=f"查询历史成交失败: {error_msg}")


@app.post("/api/trade/deal_list",
          operation_id="get_deal_list",
          summary="查询当日成交", 
          description="查询交易业务账户的当日成交列表，支持代码过滤、市场过滤，包含实时成交统计")
async def get_deal_list(request: DealListRequest) -> APIResponse:
    """查询当日成交 - 获取账户当日成交记录，包含买卖分析和时间分布"""
    if not _server_ready or not futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await futu_service.get_deal_list(request)
    except Exception as e:
        logger.error(f"查询当日成交异常: {str(e)}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        elif "当日成交" in error_msg or "成交" in error_msg:
            error_msg = "当日成交数据获取失败，请检查账户权限或网络连接"
        
        raise HTTPException(status_code=500, detail=f"查询当日成交失败: {error_msg}")


@app.post("/api/trade/history_order_list",
          operation_id="get_history_order_list",
          summary="获取历史订单列表",
          description="查询指定时间段内的历史订单记录，支持多种过滤条件")
async def get_history_order_list(request: HistoryOrderListRequest) -> APIResponse:
    """获取历史订单列表"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_history_order_list(request)
    except Exception as e:
        logger.error(f"获取历史订单列表失败: {e}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "账户" in error_msg:
            error_msg = "账户信息有误，请检查账户ID或账户索引"
        
        return APIResponse(ret_code=-1, ret_msg=f"获取历史订单列表失败: {error_msg}", data=None)


@app.post("/api/trade/order_fee_query",
          operation_id="get_order_fee_query",
          summary="查询订单费用",
          description="查询指定订单的详细费用信息，包括佣金、印花税等")
async def get_order_fee_query(request: OrderFeeQueryRequest) -> APIResponse:
    """查询订单费用"""
    if not _server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await futu_service.get_order_fee_query(request)
    except Exception as e:
        logger.error(f"查询订单费用失败: {e}")
        
        # 如果是交易连接问题，给出更具体的错误信息
        error_msg = str(e)
        if "交易未连接" in error_msg:
            error_msg = "交易功能未启用，请确保富途OpenD已启动且支持交易功能"
        elif "密码" in error_msg.lower() or "unlock" in error_msg.lower():
            error_msg = "交易密码验证失败，请检查交易密码配置"
        elif "订单" in error_msg:
            error_msg = "订单信息有误，请检查订单ID是否正确"
        
        return APIResponse(ret_code=-1, ret_msg=f"查询订单费用失败: {error_msg}", data=None)


@app.post("/api/trade/trade_history",
          operation_id="get_trade_history",
          summary="获取交易历史",
          description="获取历史成交记录（history_deal_list的别名接口）")
async def get_trade_history(request: HistoryDealListRequest) -> APIResponse:
    """获取交易历史（历史成交的别名）"""
    return await get_history_deal_list(request)


# ==================== 注意事项 ====================
# 注意：富途API中没有"持仓历史"接口，持仓历史需要通过历史成交数据计算得出
# 当前持仓只能通过 position_list_query 获取当前时点的持仓信息

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
# 注释掉原来的MCP创建代码，移到lifespan中
# mcp = FastApiMCP(
#     app,
#     name="富途证券增强版MCP服务",
#     description="增强版富途证券API服务，集成15+技术指标、智能缓存系统、专业量化分析功能。支持港股、美股、A股实时报价，K线数据，技术分析指标计算，智能缓存优化，交易历史查询等功能。注意：持仓历史需通过历史成交数据计算。"
# )
# 
# # 挂载MCP服务到FastAPI应用
# mcp.mount()

if __name__ == "__main__":
    logger.info("🚀 启动富途MCP增强服务...")
    
    uvicorn.run(
        "main_enhanced:app",
        host="0.0.0.0",
        port=8001,  # 使用不同端口避免冲突
        reload=False,  # 关闭reload避免初始化问题
        log_level="info"
    )