#!/usr/bin/env python3
"""
富途MCP服务增强版 - 修复MCP Streamable HTTP协议支持
支持LobeChat等客户端的MCP Streamable HTTP协议（2025-03-26规范）
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger as log
from contextlib import asynccontextmanager
from decimal import Decimal
# from futu import *  # 注释掉，避免类型冲突

# 确保使用loguru logger
logger = log

# 导入原有模块
from services.futu_service import FutuService
from models.futu_models import *
from models.analysis_models import *
from config import settings

# 导入AI服务模块
from services.fundamental_service import fundamental_service
from services.kimi_service import kimi_service
from services.recommendation_storage import RecommendationStorageService
from models.recommendation_models import RecommendationWriteRequest, RecommendationQueryRequest

# 自定义JSON编码器
def json_serial(obj):
    """JSON序列化器，处理datetime等特殊类型"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

# 导入新功能模块  
from cache.cache_manager import DataCacheManager, CacheConfig
from analysis.technical_indicators import TechnicalIndicators, TechnicalData, IndicatorConfig

# 全局变量
futu_service: Optional[FutuService] = None
cache_manager: Optional[DataCacheManager] = None
_server_ready = False
_mcp_ready = False
recommendation_storage: RecommendationStorageService = None

# MCP工具定义
MCP_TOOLS = [
    {
        "name": "get_stock_quote",
        "description": "获取股票实时报价信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "股票代码列表，如 ['HK.00700', 'HK.09660']"
                },
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code_list"]
        }
    },
    {
        "name": "read_webpage",
        "description": "📄 网页内容读取 - 通过metaso reader API读取任意网页的纯文本内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要读取的网页URL，如'https://www.163.com/news/article/K56809DQ000189FH.html'"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "chat_completion",
        "description": "💬 智能问答对话 - 通过metaso chat API进行流式问答对话",
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "description": "消息角色：user/assistant/system"},
                            "content": {"type": "string", "description": "消息内容"}
                        },
                        "required": ["role", "content"]
                    },
                    "description": "对话消息列表，格式：[{'role': 'user', 'content': '问题内容'}]"
                },
                "model": {"type": "string", "default": "fast", "description": "模型类型：fast/normal"},
                "stream": {"type": "boolean", "default": True, "description": "是否流式响应"}
            },
            "required": ["messages"]
        }
    },
    {
        "name": "get_kimi_chat",
        "description": "🔥 Kimi对话 - 通过月之暗面官方 API 驱动 kimi-k2-thinking-turbo 模型进行智能对话",
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "description": "消息角色：user/assistant/system"},
                            "content": {"type": "string", "description": "消息内容"}
                        },
                        "required": ["role", "content"]
                    },
                    "description": "对话消息列表，格式：[{'role': 'user', 'content': '问题内容'}]"
                },
                "model": {"type": "string", "default": "kimi-k2-thinking-turbo", "description": "模型类型，默认kimi-k2-thinking-turbo"},
                "temperature": {"type": "number", "default": 0.7, "description": "温度参数，控制随机性(0-1)"},
                "max_tokens": {"type": "integer", "default": 2048, "description": "最大生成token数"}
            },
            "required": ["messages"]
        }
    },
    {
        "name": "get_history_kline",
        "description": "获取历史K线数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "ktype": {"type": "string", "default": "K_DAY", "description": "K线类型：K_1M, K_5M, K_15M, K_30M, K_60M, K_DAY, K_WEEK, K_MON"},
                "start": {"type": "string", "description": "开始日期，格式：YYYY-MM-DD"},
                "end": {"type": "string", "description": "结束日期，格式：YYYY-MM-DD"},
                "max_count": {"type": "integer", "description": "最大返回数量"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_technical_indicators",
        "description": "计算技术分析指标",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["all"],
                    "description": "指标列表：['macd', 'rsi', 'bollinger_bands', 'kdj', 'all']"
                },
                "ktype": {"type": "string", "default": "K_DAY", "description": "K线类型"},
                "period": {"type": "integer", "description": "计算周期"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_order_book",
        "description": "获取买盘卖盘数据（摆盘）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "num": {"type": "integer", "default": 10, "description": "档位数量，默认10档"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_rt_ticker",
        "description": "获取逐笔交易数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "num": {"type": "integer", "default": 100, "description": "获取条数，默认100条"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_rt_data",
        "description": "获取实时分时数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_market_snapshot",
        "description": "获取市场快照（多标的）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "股票代码列表，如 ['HK.00700','US.AAPL']"
                },
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code_list"]
        }
    },
    {
        "name": "get_current_kline",
        "description": "获取当前K线数据（最近N根）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 'HK.00700'"},
                "num": {"type": "integer", "default": 100, "description": "返回数据点数量"},
                "ktype": {"type": "string", "default": "K_DAY", "description": "K线类型：K_1M/K_5M/K_DAY/K_WEEK/K_MON 等"},
                "autype": {"type": "string", "default": "qfq", "description": "复权类型：qfq/hfq/None"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_broker_queue",
        "description": "获取经纪队列（买卖盘经纪）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 'HK.00700'"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_capital_flow",
        "description": "获取资金流向数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "period_type": {"type": "string", "default": "INTRADAY", "description": "周期类型：INTRADAY(实时), DAY(日), WEEK(周), MONTH(月)"},
                "start": {"type": "string", "description": "开始日期，格式：YYYY-MM-DD"},
                "end": {"type": "string", "description": "结束日期，格式：YYYY-MM-DD"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_capital_distribution",
        "description": "获取资金分布数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_deal_list",
        "description": "获取当日成交明细",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码过滤，如 HK.00700"},
                "deal_market": {"type": "string", "description": "市场过滤：HK/US/CN"},
                "trd_env": {"type": "string", "default": "REAL", "description": "交易环境：SIMULATE(模拟)/REAL(真实)"},
                "acc_id": {"type": "integer", "default": 0, "description": "账户ID"},
                "acc_index": {"type": "integer", "default": 0, "description": "账户序号"},
                "refresh_cache": {"type": "boolean", "default": False, "description": "是否刷新缓存"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            }
        }
    },
    {
        "name": "get_history_deal_list",
        "description": "获取历史成交明细",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码过滤，如 HK.00700"},
                "deal_market": {"type": "string", "description": "市场过滤：HK/US/CN"},
                "start": {"type": "string", "description": "开始时间，格式：YYYY-MM-DD HH:MM:SS"},
                "end": {"type": "string", "description": "结束时间，格式：YYYY-MM-DD HH:MM:SS"},
                "trd_env": {"type": "string", "default": "REAL", "description": "交易环境：仅支持REAL(真实)"},
                "acc_id": {"type": "integer", "default": 0, "description": "账户ID"},
                "acc_index": {"type": "integer", "default": 0, "description": "账户序号"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            }
        }
    },
    {
        "name": "get_position_list",
        "description": "获取持仓明细",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码过滤，如 HK.00700"},
                "position_market": {"type": "string", "description": "市场过滤：HK/US/CN"},
                "trd_env": {"type": "string", "default": "REAL", "description": "交易环境：SIMULATE(模拟)/REAL(真实)"},
                "acc_id": {"type": "integer", "default": 0, "description": "账户ID"},
                "acc_index": {"type": "integer", "default": 0, "description": "账户序号"},
                "refresh_cache": {"type": "boolean", "default": False, "description": "是否刷新缓存"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            }
        }
    },
    {
        "name": "get_acc_info",
        "description": "获取账户资金信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "currency": {"type": "string", "description": "币种：HKD/USD/CNH/JPY"},
                "trd_env": {"type": "string", "default": "REAL", "description": "交易环境：SIMULATE(模拟)/REAL(真实)"},
                "acc_id": {"type": "integer", "default": 0, "description": "账户ID"},
                "acc_index": {"type": "integer", "default": 0, "description": "账户序号"},
                "refresh_cache": {"type": "boolean", "default": False, "description": "是否刷新缓存"},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "only_essential_fields": {"type": "boolean", "default": True}
                    }
                }
            }
        }
    },
    {
        "name": "get_cache_status",
        "description": "获取缓存系统状态",
        "inputSchema": {
            "type": "object",
            "properties": {
                "detailed": {"type": "boolean", "default": False, "description": "是否返回详细信息"}
            }
        }
    },
    {
        "name": "get_fundamental_search",
        "description": "🔍 基本面信息搜索 - 通过metaso搜索API获取股票相关基本面信息、新闻和分析",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜索关键词，如'影响小米股价的相关信息'"},
                "scope": {"type": "string", "default": "webpage", "description": "搜索范围：webpage(网页)/news(新闻)/all(全部)"},
                "includeSummary": {"type": "boolean", "default": False, "description": "是否包含摘要"},
                "size": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50, "description": "返回结果数量(1-50)"},
                "includeRawContent": {"type": "boolean", "default": False, "description": "是否包含原始内容"},
                "conciseSnippet": {"type": "boolean", "default": False, "description": "是否使用简洁摘要"}
            },
            "required": ["q"]
        }
    },
    {
        "name": "get_stock_fundamental",
        "description": "🔍 股票基本面搜索 - 搜索特定股票的基本面信息，自动构建搜索关键词",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stock_code": {"type": "string", "description": "股票代码，如'HK.00700'或'00700'"},
                "stock_name": {"type": "string", "description": "股票名称，如'腾讯控股'或'小米集团'"}
            },
            "required": ["stock_code"]
        }
    },
    {
        "name": "read_webpage",
        "description": "📄 网页内容读取 - 通过metaso reader API读取任意网页的纯文本内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要读取的网页URL，如'https://www.163.com/news/article/K56809DQ000189FH.html'"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "chat_completion",
        "description": "💬 智能问答对话 - 通过metaso chat API进行流式问答对话",
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "description": "消息角色：user/assistant/system"},
                            "content": {"type": "string", "description": "消息内容"}
                        },
                        "required": ["role", "content"]
                    },
                    "description": "对话消息列表，格式：[{'role': 'user', 'content': '问题内容'}]"
                },
                "model": {"type": "string", "default": "fast", "description": "模型类型：fast/normal"},
                "stream": {"type": "boolean", "default": True, "description": "是否流式响应"}
            },
            "required": ["messages"]
        }
    },
    {
        "name": "save_recommendation",
        "description": "保存股票操作建议与依据，便于后续验证与复盘",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 HK.00700"},
                "action": {"type": "string", "enum": ["BUY","SELL","HOLD","EXIT","ADD","REDUCE","WATCH"], "description": "操作类型"},
                "rationale": {"type": "string", "description": "建议依据/理由"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "信心度(0-1)"},
                "timeframe": {"type": "string", "description": "适用时间框架"},
                "adopted": {"type": "boolean", "description": "是否已采纳"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "标签数组"},
                "source": {"type": "string", "description": "来源，模型或分析师"},
                "evidence": {"type": "array", "items": {}, "description": "证据列表（文本/对象）"},
                "adopted_at": {"type": "string", "description": "采纳时间(ISO8601)"},
                "outcome": {"type": "object", "description": "结果复盘对象"}
            },
            "required": ["code", "action", "rationale"]
        }
    },
    {
        "name": "get_recommendations",
        "description": "按条件查询股票操作建议记录（支持代码/操作/采纳/时间等过滤）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "action": {"type": "string"},
                "adopted": {"type": "boolean"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "tag": {"type": "string"},
                "source": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                "offset": {"type": "integer", "minimum": 0}
            }
        }
    }
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global futu_service, cache_manager, _server_ready, _mcp_ready
    
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
        # 初始化推荐存储服务
        global recommendation_storage
        recommendation_storage = RecommendationStorageService(db_path="data/recommendations.db")
        logger.info("✅ 推荐存储服务初始化成功")
        
        # 尝试连接富途OpenD
        if await futu_service.connect():
            logger.info("✅ 富途OpenD连接成功")
        else:
            logger.warning("⚠️  富途OpenD连接失败，部分功能可能不可用")
        
        # 等待服务完全初始化
        await asyncio.sleep(3)
        
        _server_ready = True
        _mcp_ready = True
        logger.info("✅ 增强版 MCP 服务器初始化完成")
            
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        logger.exception("详细错误信息:")
        raise
    finally:
        # 清理资源
        _server_ready = False
        _mcp_ready = False
        if futu_service:
            await futu_service.disconnect()
        logger.info("🔥 服务已停止")


# 创建FastAPI应用
app = FastAPI(
    title="富途 MCP 增强服务",
    description="集成智能缓存、技术分析、形态识别等功能的专业股票分析平台",
    version="2.0.2",
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
        "status": "healthy" if _server_ready else "starting",
        "futu_connected": _server_ready,
        "cache_available": cache_manager is not None,
        "mcp_ready": _mcp_ready,
        "timestamp": datetime.now().isoformat(),
        "cache_stats": cache_stats
    }


# ==================== MCP Streamable HTTP 协议实现 ====================
@app.get("/mcp")
async def mcp_get():
    """MCP GET方法 - 返回服务器信息"""
    payload = {
        "jsonrpc": "2.0",
        "id": None,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "富途证券增强版MCP服务",
                "version": "2.0.2"
            }
        }
    }
    return Response(content=json.dumps(payload, ensure_ascii=False), media_type="application/json")


@app.post("/mcp")
async def mcp_post(request: Request):
    """MCP POST方法 - 处理JSON-RPC请求"""
    return await handle_mcp_request(request)

@app.options("/mcp")
async def mcp_options():
    # CORS预检请求直接返回
    return Response(status_code=204)


# ==================== 根路径MCP支持（兼容性） ====================
@app.get("/")
async def root_get():
    """根路径GET方法 - 返回服务器信息"""
    payload = {
        "jsonrpc": "2.0",
        "id": None,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "富途证券增强版MCP服务",
                "version": "2.0.2"
            }
        }
    }
    return Response(content=json.dumps(payload, ensure_ascii=False), media_type="application/json")


@app.post("/")
async def root_post(request: Request):
    """根路径POST方法 - 处理JSON-RPC请求"""
    return await handle_mcp_request(request)

@app.options("/")
async def root_options():
    # CORS预检请求直接返回
    return Response(status_code=204)


async def handle_mcp_request(request: Request):
    """MCP请求处理函数"""
    try:
        # 解析JSON-RPC请求
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        logger.info(f"收到MCP请求: {method}, ID: {request_id}")
        
        # 处理不同的MCP方法
        if method == "initialize":
            return await handle_initialize(params, request_id)
        elif method == "tools/list":
            return await handle_tools_list(params, request_id)
        elif method == "tools/call":
            return await handle_tools_call(params, request_id)
        elif method == "notifications/list":
            return await handle_notifications_list(params, request_id)
        else:
            return create_error_response(request_id, -32601, f"Method not found: {method}")
            
    except json.JSONDecodeError:
        return create_error_response(None, -32700, "Parse error")
    except Exception as e:
        logger.error(f"MCP请求处理错误: {e}")
        return create_error_response(None, -32603, f"Internal error: {str(e)}")


def create_error_response(request_id: Optional[str], code: int, message: str):
    """创建错误响应"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }


async def handle_initialize(params: Dict, request_id: str):
    """处理initialize请求"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "富途证券增强版MCP服务",
                "version": "2.0.2"
            }
        }
    }


async def handle_tools_list(params: Dict, request_id: str):
    """处理tools/list请求"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": MCP_TOOLS
        }
    }


async def handle_tools_call(params: Dict, request_id: str):
    """处理tools/call请求"""
    try:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"调用工具: {tool_name}, 参数: {arguments}")
        
        # 根据工具名称调用相应的功能
        if tool_name == "get_stock_quote":
            result = await call_get_stock_quote(arguments)
        elif tool_name == "get_history_kline":
            result = await call_get_history_kline(arguments)
        elif tool_name == "get_technical_indicators":
            result = await call_get_technical_indicators(arguments)
        elif tool_name == "get_order_book":
            result = await call_get_order_book(arguments)
        elif tool_name == "get_rt_ticker":
            result = await call_get_rt_ticker(arguments)
        elif tool_name == "get_rt_data":
            result = await call_get_rt_data(arguments)
        elif tool_name == "get_market_snapshot":
            result = await call_get_market_snapshot(arguments)
        elif tool_name == "get_current_kline":
            result = await call_get_current_kline(arguments)
        elif tool_name == "get_broker_queue":
            result = await call_get_broker_queue(arguments)
        elif tool_name == "get_capital_flow":
            result = await call_get_capital_flow(arguments)
        elif tool_name == "get_capital_distribution":
            result = await call_get_capital_distribution(arguments)
        elif tool_name == "get_deal_list":
            result = await call_get_deal_list(arguments)
        elif tool_name == "get_history_deal_list":
            result = await call_get_history_deal_list(arguments)
        elif tool_name == "get_position_list":
            result = await call_get_position_list(arguments)
        elif tool_name == "get_acc_info":
            result = await call_get_acc_info(arguments)
        elif tool_name == "get_cache_status":
            result = await call_get_cache_status(arguments)
        elif tool_name == "get_fundamental_search":
            result = await call_get_fundamental_search(arguments)
        elif tool_name == "get_stock_fundamental":
            result = await call_get_stock_fundamental(arguments)
        elif tool_name == "read_webpage":
            result = await call_read_webpage(arguments)
        elif tool_name == "get_cache_status":
            result = await call_get_cache_status(arguments)
        elif tool_name == "get_fundamental_search":
            result = await call_get_fundamental_search(arguments)
        elif tool_name == "get_stock_fundamental":
            result = await call_get_stock_fundamental(arguments)
        elif tool_name == "read_webpage":
            result = await call_read_webpage(arguments)
        elif tool_name == "chat_completion":
            result = await call_chat_completion(arguments)
        elif tool_name == "get_kimi_chat":
            result = await call_get_kimi_chat(arguments)
        elif tool_name == "save_recommendation":
            result = await call_save_recommendation(arguments)
        elif tool_name == "get_recommendations":
            result = await call_get_recommendations(arguments)
        else:
            raise ValueError(f"未知工具: {tool_name}")
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2, default=json_serial)
                    }
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"工具调用错误: {e}")
        return create_error_response(request_id, -32603, f"Tool execution error: {str(e)}")


async def handle_notifications_list(params: Dict, request_id: str):
    """处理notifications/list请求"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "notifications": []
        }
    }


# ==================== 工具调用实现 ====================
async def call_get_stock_quote(arguments: Dict) -> Dict:
    """调用股票报价功能"""
    code_list = arguments.get("code_list", [])
    optimization = arguments.get("optimization", {})
    
    if not code_list:
        raise ValueError("股票代码列表不能为空")
    
    # 创建请求对象
    request = StockQuoteRequest(code_list=code_list, optimization=optimization)
    
    # 调用富途服务
    result = await futu_service.get_stock_quote(request)
    return result.dict()


async def call_get_history_kline(arguments: Dict) -> Dict:
    """调用历史K线功能"""
    # 从参数中读取字段（带中文注释）
    code = arguments.get("code")
    ktype = arguments.get("ktype", "K_DAY")
    start = arguments.get("start")
    end = arguments.get("end")
    # 兼容未传 max_count 的情况，避免将 None 传给 Pydantic 导致类型校验错误
    max_count_arg = arguments.get("max_count")
    if max_count_arg is None or max_count_arg == "":
        max_count = 100  # 使用模型默认值
    else:
        # 尝试将入参转换为整数，非法时回退默认值
        try:
            max_count = int(max_count_arg)
        except (TypeError, ValueError):
            max_count = 100
    
    if not code:
        raise ValueError("股票代码不能为空")
    
    # 创建请求对象
    request = HistoryKLineRequest(
        code=code,
        ktype=ktype,
        start=start,
        end=end,
        max_count=max_count
    )
    
    # 调用富途服务
    result = await futu_service.get_history_kline(request)
    return result.dict()


async def call_get_technical_indicators(arguments: Dict) -> Dict:
    """调用技术指标功能"""
    code = arguments.get("code")
    indicators = arguments.get("indicators", ["all"])
    ktype = arguments.get("ktype", "K_DAY")
    period = arguments.get("period")
    
    if not code:
        raise ValueError("股票代码不能为空")
    
    try:
        # 首先获取K线数据
        kline_request = HistoryKLineRequest(
            code=code,
            ktype=ktype,
            max_count=100  # 获取足够的数据用于计算指标
        )
        
        kline_result = await futu_service.get_history_kline(kline_request)
        
        if kline_result.ret_code != 0 or not kline_result.data.get("kline_data"):
            raise ValueError("无法获取K线数据")
        
        kline_data = kline_result.data["kline_data"]
        
        # 创建技术分析对象
        tech_data = TechnicalIndicators.from_kline_data(kline_data)
        
        # 计算指标
        if "all" in indicators:
            # 计算所有指标
            all_indicators = tech_data.calculate_all_indicators()
            result = all_indicators
        else:
            # 根据请求的指标计算
            result = {}
            
            # 趋势指标
            if any(indicator in indicators for indicator in ["macd", "moving_averages", "ema", "adx"]):
                trend_indicators = tech_data._calculate_trend_indicators()
                for indicator in indicators:
                    if indicator in trend_indicators:
                        result[indicator] = trend_indicators[indicator]
            
            # 动量指标
            if any(indicator in indicators for indicator in ["rsi", "kdj"]):
                momentum_indicators = tech_data._calculate_momentum_indicators()
                for indicator in indicators:
                    if indicator in momentum_indicators:
                        result[indicator] = momentum_indicators[indicator]
            
            # 波动性指标
            if any(indicator in indicators for indicator in ["bollinger_bands", "atr"]):
                volatility_indicators = tech_data._calculate_volatility_indicators()
                for indicator in indicators:
                    if indicator in volatility_indicators:
                        result[indicator] = volatility_indicators[indicator]
            
            # 成交量指标
            if any(indicator in indicators for indicator in ["obv", "vwap"]):
                volume_indicators = tech_data._calculate_volume_indicators()
                for indicator in indicators:
                    if indicator in volume_indicators:
                        result[indicator] = volume_indicators[indicator]
        
        return {
            "ret_code": 0,
            "ret_msg": "技术指标计算成功",
            "data": result,
            "code": code,
            "ktype": ktype,
            "indicators": indicators
        }
        
    except Exception as e:
        logger.error(f"技术指标计算失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"技术指标计算失败: {str(e)}",
            "data": {}
        }


async def call_get_order_book(arguments: Dict) -> Dict:
    """调用买盘卖盘功能"""
    code = arguments.get("code")
    num = arguments.get("num", 10)
    optimization = arguments.get("optimization", {})
    
    if not code:
        raise ValueError("股票代码不能为空")
    
    # 创建请求对象
    request = OrderBookRequest(code=code, num=num, optimization=optimization)
    
    # 调用富途服务
    result = await futu_service.get_order_book(request)
    return result.dict()


async def call_get_rt_ticker(arguments: Dict) -> Dict:
    """调用逐笔交易功能"""
    code = arguments.get("code")
    num = arguments.get("num", 100)
    optimization = arguments.get("optimization", {})
    
    if not code:
        raise ValueError("股票代码不能为空")
    
    # 创建请求对象
    request = TickerRequest(code=code, num=num, optimization=optimization)
    
    # 调用富途服务
    result = await futu_service.get_rt_ticker(request)
    return result.dict()


async def call_get_rt_data(arguments: Dict) -> Dict:
    """调用实时分时功能"""
    code = arguments.get("code")
    optimization = arguments.get("optimization", {})
    
    if not code:
        raise ValueError("股票代码不能为空")
    
    # 创建请求对象
    request = RTDataRequest(code=code, optimization=optimization)
    
    # 调用富途服务
    result = await futu_service.get_rt_data(request)
    return result.dict()


async def call_get_market_snapshot(arguments: Dict) -> Dict:
    """调用市场快照功能"""
    code_list = arguments.get("code_list", [])
    optimization = arguments.get("optimization", {})
    if not code_list or not isinstance(code_list, list):
        raise ValueError("股票代码列表不能为空")
    request = MarketSnapshotRequest(code_list=code_list, optimization=optimization)
    result = await futu_service.get_market_snapshot(request)
    return result.dict()


async def call_get_current_kline(arguments: Dict) -> Dict:
    """调用当前K线功能"""
    code = arguments.get("code")
    num = int(arguments.get("num", 100))
    ktype = arguments.get("ktype", "K_DAY")
    autype = arguments.get("autype", "qfq")
    optimization = arguments.get("optimization", {})
    if not code:
        raise ValueError("股票代码不能为空")
    request = CurrentKLineRequest(code=code, num=num, ktype=ktype, autype=autype, optimization=optimization)
    result = await futu_service.get_current_kline(request)
    return result.dict()


async def call_get_broker_queue(arguments: Dict) -> Dict:
    """调用经纪队列功能"""
    code = arguments.get("code")
    optimization = arguments.get("optimization", {})
    if not code:
        raise ValueError("股票代码不能为空")
    request = BrokerQueueRequest(code=code, optimization=optimization)
    result = await futu_service.get_broker_queue(request)
    return result.dict()


async def call_get_capital_flow(arguments: Dict) -> Dict:
    """调用资金流向功能"""
    code = arguments.get("code")
    period_type = arguments.get("period_type", "INTRADAY")
    start = arguments.get("start")
    end = arguments.get("end")
    optimization = arguments.get("optimization", {})
    
    if not code:
        raise ValueError("股票代码不能为空")
    
    # 创建请求对象
    request = CapitalFlowRequest(
        code=code,
        period_type=period_type,
        start=start,
        end=end,
        optimization=optimization
    )
    
    # 调用富途服务
    result = await futu_service.get_capital_flow(request)
    return result.dict()


async def call_get_capital_distribution(arguments: Dict) -> Dict:
    """调用资金分布功能"""
    code = arguments.get("code")
    optimization = arguments.get("optimization", {})
    
    if not code:
        raise ValueError("股票代码不能为空")
    
    # 创建请求对象
    request = CapitalDistributionRequest(
        code=code,
        optimization=optimization
    )
    
    # 调用富途服务
    result = await futu_service.get_capital_distribution(request)
    return result.dict()


async def call_get_deal_list(arguments: Dict) -> Dict:
    """调用当日成交明细功能"""
    code = arguments.get("code")
    deal_market = arguments.get("deal_market")
    trd_env = arguments.get("trd_env", "SIMULATE")
    acc_id = arguments.get("acc_id", 0)
    acc_index = arguments.get("acc_index", 0)
    refresh_cache = arguments.get("refresh_cache", False)
    optimization = arguments.get("optimization", {})
    
    # 创建请求对象
    request = DealListRequest(
        code=code,
        deal_market=deal_market,
        trd_env=trd_env,
        acc_id=acc_id,
        acc_index=acc_index,
        refresh_cache=refresh_cache,
        optimization=optimization
    )
    
    # 调用富途服务
    result = await futu_service.get_deal_list(request)
    return result.dict()


async def call_get_history_deal_list(arguments: Dict) -> Dict:
    """调用历史成交明细功能"""
    code = arguments.get("code")
    deal_market = arguments.get("deal_market")
    start = arguments.get("start")
    end = arguments.get("end")
    trd_env = arguments.get("trd_env", "REAL")
    acc_id = arguments.get("acc_id", 0)
    acc_index = arguments.get("acc_index", 0)
    optimization = arguments.get("optimization", {})
    
    # 创建请求对象
    request = HistoryDealListRequest(
        code=code,
        deal_market=deal_market,
        start=start,
        end=end,
        trd_env=trd_env,
        acc_id=acc_id,
        acc_index=acc_index,
        optimization=optimization
    )
    
    # 调用富途服务
    result = await futu_service.get_history_deal_list(request)
    return result.dict()


async def call_get_position_list(arguments: Dict) -> Dict:
    """调用持仓明细功能"""
    code = arguments.get("code")
    position_market = arguments.get("position_market")
    trd_env = arguments.get("trd_env", "SIMULATE")
    acc_id = arguments.get("acc_id", 0)
    acc_index = arguments.get("acc_index", 0)
    refresh_cache = arguments.get("refresh_cache", False)
    optimization = arguments.get("optimization", {})
    
    # 创建请求对象
    request = PositionListRequest(
        code=code,
        position_market=position_market,
        trd_env=trd_env,
        acc_id=acc_id,
        acc_index=acc_index,
        refresh_cache=refresh_cache,
        optimization=optimization
    )
    
    # 调用富途服务
    result = await futu_service.get_position_list(request)
    return result.dict()


async def call_get_acc_info(arguments: Dict) -> Dict:
    """调用账户资金信息功能"""
    currency = arguments.get("currency")
    trd_env = arguments.get("trd_env", "SIMULATE")
    acc_id = arguments.get("acc_id", 0)
    acc_index = arguments.get("acc_index", 0)
    refresh_cache = arguments.get("refresh_cache", False)
    optimization = arguments.get("optimization", {})
    
    # 创建请求对象
    request = AccInfoRequest(
        currency=currency,
        trd_env=trd_env,
        acc_id=acc_id,
        acc_index=acc_index,
        refresh_cache=refresh_cache,
        optimization=optimization
    )
    
    # 调用富途服务
    result = await futu_service.get_acc_info(request)
    return result.dict()


async def call_get_cache_status(arguments: Dict) -> Dict:
    """调用缓存系统状态功能"""
    detailed = arguments.get("detailed", False)
    if cache_manager is None:
        return {"ret_code": -1, "ret_msg": "缓存管理器未初始化", "data": {}}
    try:
        if detailed:
            stats = await cache_manager.get_cache_stats(detailed=True)
        else:
            stats = await cache_manager.get_cache_stats()
    except TypeError:
        # 兼容不支持 detailed 参数的实现
        stats = await cache_manager.get_cache_stats()
    return {"ret_code": 0, "ret_msg": "OK", "data": stats}


async def call_save_recommendation(arguments: Dict) -> Dict:
    """保存股票操作建议与依据"""
    try:
        req = RecommendationWriteRequest(**arguments)
    except Exception as e:
        return {"ret_code": -1, "ret_msg": f"参数错误: {e}", "data": {}}
    if recommendation_storage is None:
        return {"ret_code": -1, "ret_msg": "推荐存储服务未初始化", "data": {}}
    saved = recommendation_storage.save_recommendation(req.dict())
    return {"ret_code": 0, "ret_msg": "OK", "data": saved}


async def call_get_recommendations(arguments: Dict) -> Dict:
    """查询股票操作建议记录"""
    try:
        req = RecommendationQueryRequest(**arguments)
    except Exception as e:
        return {"ret_code": -1, "ret_msg": f"参数错误: {e}", "data": []}
    if recommendation_storage is None:
        return {"ret_code": -1, "ret_msg": "推荐存储服务未初始化", "data": []}
    items = recommendation_storage.get_recommendations(req.dict())
    return {"ret_code": 0, "ret_msg": "OK", "data": items}
