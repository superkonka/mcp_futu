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
        "description": "🔥 火山引擎Kimi对话 - 通过火山引擎ark API调用kimi-k2-250905模型进行智能对话",
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
                "model": {"type": "string", "default": "kimi-k2-250905", "description": "模型类型，默认kimi-k2-250905"},
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
                "trd_env": {"type": "string", "default": "SIMULATE", "description": "交易环境：SIMULATE(模拟)/REAL(真实)"},
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
                "trd_env": {"type": "string", "default": "SIMULATE", "description": "交易环境：SIMULATE(模拟)/REAL(真实)"},
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
                "trd_env": {"type": "string", "default": "SIMULATE", "description": "交易环境：SIMULATE(模拟)/REAL(真实)"},
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
    return {
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


@app.post("/mcp")
async def mcp_post(request: Request):
    """MCP POST方法 - 处理JSON-RPC请求"""
    return await handle_mcp_request(request)


# ==================== 根路径MCP支持（兼容性） ====================
@app.get("/")
async def root_get():
    """根路径GET方法 - 返回服务器信息"""
    return {
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


@app.post("/")
async def root_post(request: Request):
    """根路径POST方法 - 处理JSON-RPC请求"""
    return await handle_mcp_request(request)


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
        else:
            return create_error_response(request_id, -32601, f"Tool not found: {tool_name}")
        
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
    """调用缓存状态功能"""
    detailed = arguments.get("detailed", False)
    
    if cache_manager:
        result = await cache_manager.get_cache_stats()
        if detailed:
            # 如果需要详细信息，可以添加更多字段
            result["detailed"] = True
    else:
        result = {"error": "缓存管理器未初始化"}
    
    return result


# ==================== 原有API接口（保持兼容性） ====================
@app.get("/api/time/current")
async def get_current_time() -> Dict[str, Any]:
    """获取当前时间信息"""
    now = datetime.now()
    
    # 计算一些常用的时间点
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=now.weekday())  # 本周一
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    return {
        "current_time": now.isoformat(),
        "timezone": "Asia/Shanghai",
        "today_start": today_start.isoformat(),
        "yesterday_start": yesterday_start.isoformat(),
        "week_start": week_start.isoformat(),
        "month_start": month_start.isoformat(),
        "timestamp": int(now.timestamp())
    }


@app.post("/api/quote/stock_quote")
async def get_stock_quote_enhanced(request: StockQuoteRequest) -> APIResponse:
    """获取股票报价（缓存增强）"""
    try:
        start_time = time.time()
        
        # 调用富途服务获取报价
        result = await futu_service.get_stock_quote(
            request.code_list, 
            request.optimization
        )
        
        execution_time = time.time() - start_time
        
        return APIResponse(
            ret_code=0,
            ret_msg="获取股票报价成功",
            data=result,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"获取股票报价失败: {e}")
        return APIResponse(
            ret_code=-1,
            ret_msg=f"获取股票报价失败: {str(e)}"
        )


@app.post("/api/quote/history_kline")
async def get_history_kline_enhanced(request: HistoryKLineRequest) -> APIResponse:
    """获取历史K线（缓存增强）"""
    try:
        start_time = time.time()
        
        # 调用富途服务获取K线
        result = await futu_service.get_history_kline(
            request.code,
            request.ktype,
            request.start,
            request.end,
            request.max_count
        )
        
        execution_time = time.time() - start_time
        
        return APIResponse(
            ret_code=0,
            ret_msg="获取历史K线成功",
            data=result,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"获取历史K线失败: {e}")
        return APIResponse(
            ret_code=-1,
            ret_msg=f"获取历史K线失败: {str(e)}"
        )


@app.post("/api/analysis/technical_indicators")
async def get_technical_indicators(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """获取技术分析指标"""
    try:
        start_time = time.time()
        
        # 创建技术指标计算器
        tech_indicators = TechnicalIndicators()
        
        # 计算指标
        result = await tech_indicators.calculate_indicators(
            request.code,
            request.indicators,
            request.ktype,
            request.period
        )
        
        execution_time = time.time() - start_time
        
        return {
            "ret_code": 0,
            "ret_msg": "技术指标计算成功",
            "data": result,
            "execution_time": execution_time
        }
        
    except Exception as e:
        logger.error(f"技术指标计算失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"技术指标计算失败: {str(e)}"
        }


@app.get("/api/cache/status")
async def get_cache_status(detailed: bool = False) -> Dict[str, Any]:
    """获取缓存状态"""
    try:
        if cache_manager:
            result = await cache_manager.get_cache_stats(detailed)
            return {
                "ret_code": 0,
                "ret_msg": "获取缓存状态成功",
                "data": result
            }
        else:
            return {
                "ret_code": -1,
                "ret_msg": "缓存管理器未初始化"
            }
    except Exception as e:
        logger.error(f"获取缓存状态失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"获取缓存状态失败: {str(e)}"
        }


# ==================== 基本面搜索工具实现 ====================

async def call_get_fundamental_search(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具：基本面信息搜索"""
    try:
        # 构建搜索请求
        request_data = {
            "q": arguments.get("q", ""),
            "scope": arguments.get("scope", "webpage"),
            "includeSummary": arguments.get("includeSummary", False),
            "size": arguments.get("size", 10),
            "includeRawContent": arguments.get("includeRawContent", False),
            "conciseSnippet": arguments.get("conciseSnippet", False)
        }
        
        # 调用基本面搜索服务
        from models.fundamental_models import FundamentalSearchRequest
        from services.fundamental_service import fundamental_service
        
        request = FundamentalSearchRequest(**request_data)
        response = await fundamental_service.search_fundamental_info(request)
        
        return {
            "ret_code": 0,
            "ret_msg": "基本面搜索成功",
            "data": response.dict()
        }
        
    except Exception as e:
        logger.error(f"MCP基本面搜索失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"基本面搜索失败: {str(e)}",
            "data": None
        }


async def call_get_stock_fundamental(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具：股票基本面搜索"""
    try:
        stock_code = arguments.get("stock_code", "")
        stock_name = arguments.get("stock_name", "")
        
        if not stock_code:
            return {
                "ret_code": -1,
                "ret_msg": "股票代码不能为空",
                "data": None
            }
        
        # 调用股票基本面搜索服务
        from services.fundamental_service import fundamental_service
        result = await fundamental_service.search_stock_fundamental(stock_code, stock_name)
        
        return result.dict()
        
    except Exception as e:
        logger.error(f"MCP股票基本面搜索失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"股票基本面搜索失败: {str(e)}",
            "data": None
        }


async def call_read_webpage(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具：网页内容读取"""
    try:
        url = arguments.get("url", "")
        if not url:
            return {
                "ret_code": -1,
                "ret_msg": "网页URL不能为空",
                "data": None
            }
        
        # 调用网页读取服务
        from services.fundamental_service import fundamental_service
        content = await fundamental_service.read_webpage(url)
        
        return {
            "ret_code": 0,
            "ret_msg": "网页读取成功",
            "data": {
                "url": url,
                "content": content,
                "content_length": len(content),
                "api_source": "metaso"
            }
        }
        
    except Exception as e:
        logger.error(f"MCP网页读取失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"网页读取失败: {str(e)}",
            "data": None
        }


async def call_chat_completion(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具：智能问答对话"""
    try:
        messages = arguments.get("messages", [])
        model = arguments.get("model", "fast")
        stream = arguments.get("stream", True)
        
        if not messages:
            return {
                "ret_code": -1,
                "ret_msg": "对话消息不能为空",
                "data": None
            }
        
        # 调用问答服务
        from services.fundamental_service import fundamental_service
        answer = await fundamental_service.chat_completion(messages, model, stream)
        
        return {
            "ret_code": 0,
            "ret_msg": "问答成功",
            "data": {
                "answer": answer,
                "model": model,
                "stream": stream,
                "messages": messages,
                "api_source": "metaso"
            }
        }
        
    except Exception as e:
        logger.error(f"MCP问答失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"问答失败: {str(e)}",
            "data": None
        }


# ==================== Metaso网页读取工具实现 ====================

async def call_read_webpage(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具：网页内容读取"""
    try:
        url = arguments.get("url", "")
        
        if not url:
            return {
                "ret_code": -1,
                "ret_msg": "网页URL不能为空",
                "data": None
            }
        
        # 调用网页读取服务
        from models.fundamental_models import MetasoReaderRequest
        
        request = MetasoReaderRequest(url=url)
        response = await fundamental_service.read_webpage(request)
        
        return {
            "ret_code": 0,
            "ret_msg": "网页读取成功",
            "data": response.dict()
        }
        
    except Exception as e:
        logger.error(f"MCP网页读取失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"网页读取失败: {str(e)}",
            "data": None
        }


# ==================== Metaso问答工具实现 ====================

async def call_chat_completion(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具：智能问答对话"""
    try:
        messages = arguments.get("messages", [])
        model = arguments.get("model", "fast")
        stream = arguments.get("stream", True)
        
        if not messages:
            return {
                "ret_code": -1,
                "ret_msg": "对话消息不能为空",
                "data": None
            }
        
        # 调用问答服务
        answer = await fundamental_service.chat_completion(messages, model, stream)
        
        return {
            "ret_code": 0,
            "ret_msg": "问答成功",
            "data": {
                "answer": answer,
                "model": model,
                "stream": stream,
                "messages": messages,
                "api_source": "metaso"
            }
        }
        
    except Exception as e:
        logger.error(f"MCP问答失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"问答失败: {str(e)}",
            "data": None
        }


# ==================== 火山引擎Kimi对话工具实现 ====================

async def call_get_kimi_chat(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具：火山引擎Kimi对话"""
    try:
        messages = arguments.get("messages", [])
        model = arguments.get("model", "kimi-k2-250905")
        temperature = arguments.get("temperature", 0.7)
        max_tokens = arguments.get("max_tokens", 2048)
        
        if not messages:
            return {
                "ret_code": -1,
                "ret_msg": "对话消息不能为空",
                "data": None
            }
        
        # 构建Kimi请求
        from models.kimi_models import KimiChatRequest, KimiChatMessage
        
        kimi_messages = [
            KimiChatMessage(role=msg["role"], content=msg["content"])
            for msg in messages
        ]
        
        request = KimiChatRequest(
            messages=kimi_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # 调用Kimi服务
        response = await kimi_service.chat_completion(request)
        
        return {
            "ret_code": 0,
            "ret_msg": "Kimi对话成功",
            "data": {
                "response": response.dict(),
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": messages,
                "api_source": "volces_kimi"
            }
        }
        
    except Exception as e:
        logger.error(f"MCP Kimi对话失败: {e}")
        return {
            "ret_code": -1,
            "ret_msg": f"Kimi对话失败: {str(e)}",
            "data": None
        }


# ==================== 启动入口 ====================
if __name__ == "__main__":
    logger.info("🚀 启动富途MCP增强服务...")
    uvicorn.run(
        "main_enhanced_mcp_fixed:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
