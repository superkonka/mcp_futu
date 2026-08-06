"""行情数据接口 —— 从 main_enhanced.py 机械拆分，行为不变。"""
from fastapi import APIRouter

from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S  # 运行期全局（服务实例 / _server_ready）

router = APIRouter()




# ==================== 原有行情接口（增强版） ====================
@router.post("/api/quote/history_kline",
          operation_id="get_history_kline_enhanced",
          summary="获取历史K线（缓存增强）",
          description="智能缓存的历史K线获取，自动从缓存优化数据获取速度")
async def get_history_kline_enhanced(request: HistoryKLineRequest) -> APIResponse:
    """获取历史K线数据（缓存增强版）"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    ktype_token, cache_start, cache_end = S._normalize_kline_cache_scope(request)
    
    try:
        # 1. 尝试从缓存获取数据
        if S.cache_manager:
            cached_data = await S.cache_manager.get_kline_data(
                request.code, ktype_token, cache_start, cache_end
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
        result = await S.futu_service.get_history_kline(request)
        
        # 3. 存储到缓存
        if result.ret_code == 0 and S.cache_manager and result.data.get("kline_data"):
            await S.cache_manager.store_kline_data(
                request.code, ktype_token,
                cache_start, cache_end,
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


@router.post("/api/quote/stock_quote",
          operation_id="get_stock_quote_enhanced", 
          summary="获取股票报价（缓存增强）")
async def get_stock_quote_enhanced(request: StockQuoteRequest) -> APIResponse:
    """获取股票报价（缓存增强版）"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # 1. 尝试从缓存获取
        if S.cache_manager:
            cached_data = await S.cache_manager.get_quote_data(request.code_list)
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
        result = await S.futu_service.get_stock_quote(request)
        
        # 3. 存储到缓存
        if result.ret_code == 0 and S.cache_manager and result.data.get("quotes"):
            await S.cache_manager.store_quote_data(request.code_list, result.data["quotes"])
        
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


# ==================== 原有接口保持兼容 ====================
@router.post("/api/quote/stock_basicinfo",
          operation_id="get_stock_basicinfo",
          summary="获取股票基本信息",
          description="获取指定市场和证券类型的股票基本信息列表")
async def get_stock_basicinfo(request: StockBasicInfoRequest) -> APIResponse:
    """获取股票基本信息"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await S.futu_service.get_stock_basicinfo(request)
    except Exception as e:
        logger.error(f"获取股票基本信息失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取股票基本信息失败: {e}", data=None)


@router.post("/api/quote/trading_days", 
          operation_id="get_trading_days",
          summary="获取交易日",
          description="获取指定市场在指定时间段内的交易日列表")
async def get_trading_days(request: TradingDaysRequest) -> APIResponse:
    """获取交易日 - 查询指定时间段内的交易日"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await S.futu_service.get_trading_days(request)
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取交易日历失败: {e}", data=None)


@router.post("/api/quote/capital_flow", 
          operation_id="get_capital_flow",
          summary="获取资金流向",
          description="获取个股资金流向数据，包括主力、大单、中单、小单的净流入情况")
async def get_capital_flow(request: CapitalFlowRequest) -> APIResponse:
    """获取资金流向 - 分析主力资金动向和散户情绪"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await S.futu_service.get_capital_flow(request)
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取资金流向失败: {e}", data=None)


@router.post("/api/quote/capital_distribution", 
          operation_id="get_capital_distribution",
          summary="获取资金分布",
          description="获取个股当前资金分布情况，分析特大单、大单、中单、小单的流入流出对比")
async def get_capital_distribution(request: CapitalDistributionRequest) -> APIResponse:
    """获取资金分布"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await S.futu_service.get_capital_distribution(request)
    except Exception as e:
        logger.error(f"获取资金分布异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取资金分布异常: {str(e)}")


@router.post("/api/quote/rehab", 
          operation_id="get_rehab",
          summary="获取复权因子",
          description="获取股票复权因子数据，包括拆股、合股、送股、转增股、配股、增发等公司行为的复权信息")
async def get_rehab(request: RehabRequest) -> APIResponse:
    """获取复权因子"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await S.futu_service.get_rehab(request)
    except Exception as e:
        logger.error(f"获取复权因子异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取复权因子异常: {str(e)}")


@router.post("/api/market/stock_filter", 
          operation_id="get_stock_filter",
          summary="条件选股",
          description="基于多种条件筛选股票，支持价格、成交量、技术指标等多维度筛选，支持板块过滤")
async def get_stock_filter(request: StockFilterRequest) -> APIResponse:
    """条件选股"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await S.futu_service.get_stock_filter(request)
    except Exception as e:
        logger.error(f"条件选股异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"条件选股异常: {str(e)}")


@router.post("/api/market/plate_stock", 
          operation_id="get_plate_stock",
          summary="获取板块内股票列表",
          description="获取指定板块内的所有股票列表，支持按字段排序")
async def get_plate_stock(request: PlateStockRequest) -> APIResponse:
    """获取板块内股票列表"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await S.futu_service.get_plate_stock(request)
    except Exception as e:
        logger.error(f"获取板块内股票列表异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取板块内股票列表异常: {str(e)}")


@router.post("/api/market/plate_list", 
          operation_id="get_plate_list",
          summary="获取板块列表",
          description="获取指定市场的板块列表，支持按板块类型过滤（行业、概念、地域板块）")
async def get_plate_list(request: PlateListRequest) -> APIResponse:
    """获取板块列表"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        return await S.futu_service.get_plate_list(request)
    except Exception as e:
        logger.error(f"获取板块列表异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取板块列表异常: {str(e)}")


# ==================== 注意事项 ====================
# 注意：富途API中没有"持仓历史"接口，持仓历史需要通过历史成交数据计算得出
# 当前持仓只能通过 position_list_query 获取当前时点的持仓信息

# ==================== MCP专用增强拉取接口 ====================

@router.post("/api/quote/realtime_quote_enhanced",
          operation_id="get_realtime_quote_enhanced",
          summary="🚀 MCP专用：增强实时报价拉取",
          description="专为MCP设计的实时报价接口，支持批量获取，无需订阅，直接拉取最新数据")
async def get_realtime_quote_enhanced(request: RealtimeQuoteEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时报价拉取"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await S.futu_service.get_realtime_quote_enhanced(request.codes, request.fields)
    except Exception as e:
        logger.error(f"获取增强实时报价失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时报价失败: {e}", data=None)


@router.post("/api/quote/realtime_orderbook_enhanced",
          operation_id="get_realtime_orderbook_enhanced",
          summary="🚀 MCP专用：增强实时摆盘拉取",
          description="专为MCP设计的实时摆盘接口，无需订阅，直接拉取买卖盘口数据")
async def get_realtime_orderbook_enhanced(request: RealtimeOrderBookEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时摆盘拉取"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await S.futu_service.get_realtime_orderbook_enhanced(request.code, request.num)
    except Exception as e:
        logger.error(f"获取增强实时摆盘失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时摆盘失败: {e}", data=None)


@router.post("/api/quote/realtime_ticker_enhanced",
          operation_id="get_realtime_ticker_enhanced",
          summary="🚀 MCP专用：增强实时逐笔拉取",
          description="专为MCP设计的实时逐笔接口，无需订阅，直接拉取最新成交数据")
async def get_realtime_ticker_enhanced(request: RealtimeTickerEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时逐笔拉取"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await S.futu_service.get_realtime_ticker_enhanced(request.code, request.num)
    except Exception as e:
        logger.error(f"获取增强实时逐笔失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时逐笔失败: {e}", data=None)


@router.post("/api/quote/realtime_data_enhanced",
          operation_id="get_realtime_data_enhanced",
          summary="🚀 MCP专用：增强实时分时拉取",
          description="专为MCP设计的实时分时接口，无需订阅，直接拉取分时走势数据")
async def get_realtime_data_enhanced(request: RealtimeDataEnhancedRequest) -> APIResponse:
    """MCP专用：增强实时分时拉取"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    
    try:
        return await S.futu_service.get_realtime_data_enhanced(request.code)
    except Exception as e:
        logger.error(f"获取增强实时分时失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"获取增强实时分时失败: {e}", data=None)
