"""系统/时间/缓存接口 —— 从 main_enhanced.py 机械拆分，行为不变。"""
from fastapi import APIRouter

from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S  # 运行期全局（服务实例 / _server_ready）

router = APIRouter()




# ==================== 时间相关接口 ====================
@router.get("/api/time/current",
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
                "next_trading_day": S._get_next_trading_day(now).strftime("%Y-%m-%d")
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


# ==================== 缓存管理接口 ====================
@router.post("/api/system/request_quote_rights",
          operation_id="request_quote_rights", 
          summary="🔧 请求最高行情权限",
          description="手动请求最高行情权限，解决权限被抢占的问题")
async def request_quote_rights() -> Dict[str, Any]:
    """手动请求最高行情权限"""
    if not S._server_ready or not S.futu_service:
        return {
            "success": False,
            "message": "服务未就绪",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # 强制检查并请求权限
        logger.info("📞 接收到手动权限请求...")
        success = await S.futu_service._check_and_ensure_quote_rights(force_check=True)
        
        return {
            "success": success,
            "message": "权限请求成功" if success else "权限请求失败，请检查OpenD连接和Telnet端口",
            "rights_checked": S.futu_service._quote_rights_checked,
            "last_check_time": S.futu_service._last_quote_rights_check,
            "auto_request_enabled": S.futu_service._quote_rights_auto_request,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"手动权限请求异常: {str(e)}")
        return {
            "success": False,
            "message": f"权限请求异常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/api/cache/status",
         operation_id="get_cache_status",
         summary="获取缓存状态")
async def get_cache_status(detailed: bool = False) -> Dict[str, Any]:
    """获取缓存状态"""
    try:
        if not S.cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        stats = await S.cache_manager.get_cache_stats()
        
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


@router.post("/api/cache/preload",
          operation_id="preload_cache_data",
          summary="预加载缓存数据")
async def preload_cache_data(request: CachePreloadRequest) -> Dict[str, Any]:
    """预加载缓存数据"""
    start_time = time.time()
    
    try:
        if not S.cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        # 执行预加载
        await S.cache_manager.preload_data(request.symbols, request.days)
        
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


@router.delete("/api/cache/clear",
           operation_id="clear_cache_data",
           summary="清理缓存数据")
async def clear_cache_data(request: CacheClearRequest) -> Dict[str, Any]:
    """清理缓存数据"""
    start_time = time.time()
    
    try:
        if not S.cache_manager:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化",
                "data": None
            }
        
        # 执行清理
        await S.cache_manager.clear_cache(request.cache_type.value)
        
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
