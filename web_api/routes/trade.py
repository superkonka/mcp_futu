"""交易查询接口 —— 从 main_enhanced.py 机械拆分，行为不变。"""
from fastapi import APIRouter

from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S  # 运行期全局（服务实例 / _server_ready）

router = APIRouter()




# ==================== 交易相关接口 ====================

@router.post("/api/trade/acc_info",
          operation_id="get_acc_info", 
          summary="查询账户资金",
          description="查询交易业务账户的资产净值、证券市值、现金、购买力等资金数据")
async def get_acc_info(request: AccInfoRequest) -> APIResponse:
    """查询账户资金 - 获取账户总资产、现金、购买力等资金信息"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not S.futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await S.futu_service.get_acc_info(request)
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


@router.post("/api/trade/position_list",
          operation_id="get_position_list",
          summary="查询持仓列表", 
          description="查询交易业务账户的持仓列表，支持代码过滤、市场过滤、盈亏比例过滤等多种筛选条件")
async def get_position_list(request: PositionListRequest) -> APIResponse:
    """查询持仓列表 - 获取账户所有持仓信息，包含盈亏分析和市场分布"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not S.futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await S.futu_service.get_position_list(request)
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


@router.post("/api/trade/history_deal_list",
          operation_id="get_history_deal_list",
          summary="查询历史成交", 
          description="查询交易业务账户的历史成交列表，支持代码过滤、市场过滤、时间范围过滤。注意：仅支持真实环境")
async def get_history_deal_list(request: HistoryDealListRequest) -> APIResponse:
    """查询历史成交 - 获取账户历史成交记录，包含买卖分析和费用统计"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not S.futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await S.futu_service.get_history_deal_list(request)
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


@router.post("/api/trade/deal_list",
          operation_id="get_deal_list",
          summary="查询当日成交", 
          description="查询交易业务账户的当日成交列表，支持代码过滤、市场过滤，包含实时成交统计")
async def get_deal_list(request: DealListRequest) -> APIResponse:
    """查询当日成交 - 获取账户当日成交记录，包含买卖分析和时间分布"""
    if not S._server_ready or not S.futu_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    if not S.futu_service.has_trade_connection():
        raise HTTPException(status_code=503, detail="交易接口未连接或未解锁，请先在OpenD中开启交易功能")
    
    try:
        return await S.futu_service.get_deal_list(request)
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


@router.post("/api/trade/history_order_list",
          operation_id="get_history_order_list",
          summary="获取历史订单列表",
          description="查询指定时间段内的历史订单记录，支持多种过滤条件")
async def get_history_order_list(request: HistoryOrderListRequest) -> APIResponse:
    """获取历史订单列表"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.futu_service or not S.futu_service.has_trade_connection():
        return APIResponse(ret_code=-1, ret_msg="交易接口未连接或未解锁，请检查OpenD状态后重试", data=None)
    
    try:
        return await S.futu_service.get_history_order_list(request)
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


@router.post("/api/trade/order_fee_query",
          operation_id="get_order_fee_query",
          summary="查询订单费用",
          description="查询指定订单的详细费用信息，包括佣金、印花税等")
async def get_order_fee_query(request: OrderFeeQueryRequest) -> APIResponse:
    """查询订单费用"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.futu_service or not S.futu_service.has_trade_connection():
        return APIResponse(ret_code=-1, ret_msg="交易接口未连接或未解锁，请检查OpenD状态后重试", data=None)
    
    try:
        return await S.futu_service.get_order_fee_query(request)
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


@router.post("/api/trade/trade_history",
          operation_id="get_trade_history",
          summary="获取交易历史",
          description="获取历史成交记录（history_deal_list的别名接口）")
async def get_trade_history(request: HistoryDealListRequest) -> APIResponse:
    """获取交易历史（历史成交的别名）"""
    return await get_history_deal_list(request)
