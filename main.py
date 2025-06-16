import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from loguru import logger
import time

from fastapi_mcp import FastApiMCP
from services.futu_service import FutuService
from models.futu_models import *

# 全局服务实例和状态管理
futu_service = FutuService()
_server_ready = False
_initialization_start_time = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _server_ready, _initialization_start_time
    
    _initialization_start_time = time.time()
    logger.info("正在初始化MCP服务...")
    
    try:
        # 启动时
        logger.info("正在连接富途OpenD...")
        connected = await futu_service.connect()
        if not connected:
            logger.error("无法连接到富途OpenD，请检查OpenD是否启动")
            raise Exception("富途OpenD连接失败")
        
        # 确保MCP服务器完全初始化
        logger.info("正在初始化MCP协议...")
        await asyncio.sleep(2)  # 给MCP服务器足够的初始化时间
        
        # 验证连接状态
        if not futu_service.is_connected:
            raise Exception("富途服务连接验证失败")
            
        _server_ready = True
        initialization_time = time.time() - _initialization_start_time
        logger.info(f"富途MCP服务启动成功 (初始化耗时: {initialization_time:.2f}秒)")
        
        yield
        
    except Exception as e:
        logger.error(f"服务初始化失败: {e}")
        _server_ready = False
        raise
    finally:
        # 关闭时
        _server_ready = False
        await futu_service.disconnect()
        logger.info("富途MCP服务已停止")

# 创建 FastAPI 应用
app = FastAPI(
    title="富途 MCP API 服务",
    description="通过 MCP 协议提供富途 API 接口",
    version="1.0.0",
    lifespan=lifespan
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加服务就绪状态检查中间件
@app.middleware("http")
async def check_server_ready(request, call_next):
    """检查服务器是否就绪"""
    
    # 完全排除MCP相关端点，避免干扰SSE协议
    excluded_paths = [
        "/health", "/ready", "/mcp", "/docs", "/openapi.json", "/redoc"
    ]
    
    # 检查是否为排除的路径或路径前缀
    request_path = request.url.path
    for excluded_path in excluded_paths:
        if request_path == excluded_path or request_path.startswith(excluded_path + "/"):
            return await call_next(request)
    
    # 对于API端点，确保服务器已就绪
    if request_path.startswith("/api/") and not _server_ready:
        logger.warning(f"服务器未就绪，拒绝请求: {request_path}")
        raise HTTPException(
            status_code=503, 
            detail={
                "error": "Service not ready",
                "message": "MCP服务器正在初始化中，请稍后重试",
                "ready": False,
                "initialization_time": time.time() - _initialization_start_time if _initialization_start_time else 0
            }
        )
    
    return await call_next(request)

# 富途API接口 - 这些将被自动转换为MCP工具
@app.post("/api/quote/stock_quote", 
          operation_id="get_stock_quote",
          summary="获取股票报价",
          description="获取指定股票代码列表的实时报价信息")
async def get_stock_quote(request: StockQuoteRequest) -> APIResponse:
    """获取股票报价 - 支持多只股票同时查询"""
    try:
        return await futu_service.get_stock_quote(request)
    except Exception as e:
        logger.error(f"获取股票报价失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票报价失败: {e}", data=None)

@app.post("/api/quote/history_kline", 
          operation_id="get_history_kline",
          summary="获取历史K线",
          description="获取指定股票的历史K线数据，支持各种时间周期和复权方式")
async def get_history_kline(request: HistoryKLineRequest) -> APIResponse:
    """获取历史K线数据 - 支持分钟、日、周、月K线"""
    try:
        return await futu_service.get_history_kline(request)
    except Exception as e:
        logger.error(f"获取历史K线失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取历史K线失败: {e}", data=None)

@app.post("/api/quote/current_kline", 
          operation_id="get_current_kline",
          summary="获取当前K线",
          description="获取指定股票的当前K线数据")
async def get_current_kline(request: CurrentKLineRequest) -> APIResponse:
    """获取当前K线数据"""
    try:
        return await futu_service.get_current_kline(request)
    except Exception as e:
        logger.error(f"获取当前K线失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取当前K线失败: {e}", data=None)

@app.post("/api/quote/market_snapshot", 
          operation_id="get_market_snapshot",
          summary="获取市场快照",
          description="获取指定股票代码列表的市场快照信息")
async def get_market_snapshot(request: MarketSnapshotRequest) -> APIResponse:
    """获取市场快照 - 包含实时价格、成交量等信息"""
    try:
        return await futu_service.get_market_snapshot(request)
    except Exception as e:
        logger.error(f"获取市场快照失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取市场快照失败: {e}", data=None)

@app.post("/api/quote/stock_basicinfo", 
          operation_id="get_stock_basicinfo",
          summary="获取股票基本信息",
          description="获取指定市场和证券类型的股票基本信息列表")
async def get_stock_basicinfo(request: StockBasicInfoRequest) -> APIResponse:
    """获取股票基本信息 - 包含股票名称、代码、上市信息等"""
    try:
        return await futu_service.get_stock_basicinfo(request)
    except Exception as e:
        logger.error(f"获取股票基本信息失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票基本信息失败: {e}", data=None)

@app.post("/api/quote/subscribe", 
          operation_id="subscribe_quotes",
          summary="订阅行情数据",
          description="订阅指定股票的实时行情推送")
async def subscribe_quotes(request: SubscribeRequest) -> APIResponse:
    """订阅行情数据 - 实时推送报价、摆盘、逐笔等数据"""
    try:
        return await futu_service.subscribe(request)
    except Exception as e:
        logger.error(f"订阅数据失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"订阅数据失败: {e}", data=None)

@app.post("/api/quote/order_book", 
          operation_id="get_order_book",
          summary="获取摆盘数据",
          description="获取指定股票的买卖档位摆盘信息")
async def get_order_book(request: OrderBookRequest) -> APIResponse:
    """获取摆盘数据 - 显示买卖档位和委托量"""
    try:
        return await futu_service.get_order_book(request)
    except Exception as e:
        logger.error(f"获取买卖盘数据失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取买卖盘数据失败: {e}", data=None)

@app.post("/api/quote/rt_ticker", 
          operation_id="get_rt_ticker",
          summary="获取逐笔数据",
          description="获取指定股票的实时逐笔成交数据")
async def get_rt_ticker(request: TickerRequest) -> APIResponse:
    """获取逐笔数据 - 显示每笔成交的详细信息"""
    try:
        return await futu_service.get_rt_ticker(request)
    except Exception as e:
        logger.error(f"获取实时逐笔数据失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取实时逐笔数据失败: {e}", data=None)

@app.post("/api/quote/rt_data", 
          operation_id="get_rt_data",
          summary="获取分时数据",
          description="获取指定股票的分时走势数据")
async def get_rt_data(request: RTDataRequest) -> APIResponse:
    """获取分时数据 - 显示股价的分时走势"""
    try:
        return await futu_service.get_rt_data(request)
    except Exception as e:
        logger.error(f"获取实时分时数据失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取实时分时数据失败: {e}", data=None)

@app.post("/api/quote/trading_days", 
          operation_id="get_trading_days",
          summary="获取交易日",
          description="获取指定市场在指定时间段内的交易日列表")
async def get_trading_days(request: TradingDaysRequest) -> APIResponse:
    """获取交易日 - 查询指定时间段内的交易日"""
    try:
        return await futu_service.get_trading_days(request)
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取交易日历失败: {e}", data=None)

# 增强的健康检查端点
@app.get("/health")
async def health_check():
    """健康检查 - 包含详细的服务状态信息"""
    current_time = time.time()
    initialization_time = current_time - _initialization_start_time if _initialization_start_time else 0
    
    return {
        "status": "healthy" if _server_ready and futu_service.is_connected else "unhealthy",
        "ready": _server_ready,
        "futu_connected": futu_service.is_connected,
        "initialization_time": f"{initialization_time:.2f}s",
        "timestamp": current_time,
        "details": {
            "server_ready": _server_ready,
            "futu_service_connected": futu_service.is_connected,
            "initialization_complete": _server_ready and futu_service.is_connected
        }
    }

# 添加就绪状态检查端点
@app.get("/ready")
async def readiness_check():
    """就绪状态检查 - 专门用于检查服务是否准备接受请求"""
    if _server_ready and futu_service.is_connected:
        return {"ready": True, "message": "Service is ready to accept requests"}
    else:
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "message": "Service is not ready",
                "server_ready": _server_ready,
                "futu_connected": futu_service.is_connected
            }
        )

# 创建并配置MCP服务
mcp = FastApiMCP(
    app,
    name="富途证券行情API的MCP服务 - 提供港股、美股、A股等市场的实时行情数据",
)

# 挂载MCP服务到FastAPI应用
mcp.mount()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    ) 