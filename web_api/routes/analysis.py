"""综合分析与技术指标接口 —— 从 main_enhanced.py 机械拆分，行为不变。"""
from fastapi import APIRouter

from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S  # 运行期全局（服务实例 / _server_ready）
from web_api.routes.quote import get_history_kline_enhanced  # 跨模块复用（原单文件内直接调用）

router = APIRouter()




# ==================== 综合分析接口 ====================
@router.post("/api/analysis/snapshot",
          operation_id="get_analysis_snapshot",
          summary="获取股票综合分析快照",
          tags=["analysis"])
async def get_analysis_snapshot(request: AnalysisSnapshotRequest) -> Dict[str, Any]:
    """返回单支股票的全量分析快照，用于 MCP/Agent 快速读取"""
    code = request.code
    logger.info(f"[analysis.snapshot] code={code} start")
    start = time.time()

    def _noop(result=None):
        return asyncio.create_task(asyncio.sleep(0, result=result))

    quote_task = asyncio.create_task(S._fetch_quote_snapshot(code))
    signals_task = asyncio.create_task(S._fetch_news_signals(code, 12)) if request.include_signals else _noop({})
    rec_task = asyncio.create_task(S._fetch_recommendations_snapshot(code)) if request.include_recommendations else _noop([])
    holding_task = asyncio.create_task(S._fetch_holding_snapshot(code)) if request.include_holding else _noop(None)

    if request.include_history and S.futu_service:
        history_task = asyncio.create_task(
            S.futu_service.get_history_kline(
                HistoryKLineRequest(
                    code=code,
                    ktype=request.history_ktype,
                    max_count=request.history_points
                )
            )
        )
    else:
        history_task = _noop()

    if request.include_capital_flow and S.futu_service:
        flow_task = asyncio.create_task(
            S.futu_service.get_capital_flow(
                CapitalFlowRequest(code=code, period_type=PeriodType.DAY)
            )
        )
    else:
        flow_task = _noop()

    if request.include_capital_distribution and S.futu_service:
        distribution_task = asyncio.create_task(
            S.futu_service.get_capital_distribution(CapitalDistributionRequest(code=code))
        )
    else:
        distribution_task = _noop()

    if request.include_technicals:
        technical_req = TechnicalAnalysisRequest(
            code=code,
            period=request.technical_period,
            indicators=request.technical_indicators
        )
        technical_task = asyncio.create_task(get_technical_indicators(technical_req))
    else:
        technical_task = _noop()

    (quote, signals, recommendations, holding,
     history_resp, flow_resp, distribution_resp, technical_resp) = await asyncio.gather(
        quote_task, signals_task, rec_task, holding_task,
        history_task, flow_task, distribution_task, technical_task
    )

    snapshot: Dict[str, Any] = {
        "code": code,
        "generated_at": datetime.now().isoformat(),
        "quote": quote,
        "session_window": S._get_session_window(code)
    }

    if request.include_signals and signals:
        snapshot["signals"] = signals
    if request.include_recommendations and recommendations:
        snapshot["recommendations"] = recommendations
    if request.include_holding and holding:
        snapshot["holding"] = holding
    if request.include_history and isinstance(history_resp, APIResponse) and history_resp.ret_code == 0:
        snapshot["history_kline"] = history_resp.data.get("kline_data")
    if request.include_capital_flow and isinstance(flow_resp, APIResponse) and flow_resp.ret_code == 0:
        snapshot["capital_flow"] = flow_resp.data
    if request.include_capital_distribution and isinstance(distribution_resp, APIResponse) and distribution_resp.ret_code == 0:
        snapshot["capital_distribution"] = distribution_resp.data
    if request.include_technicals and isinstance(technical_resp, dict) and technical_resp.get("ret_code") == 0:
        snapshot["technical_indicators"] = technical_resp.get("data")
        summary = technical_resp.get("data", {}).get("summary") if technical_resp.get("data") else None
        if summary:
            snapshot.setdefault("insights", {})["technical_summary"] = summary

    if signals:
        bullish = len(signals.get("bullish", []))
        bearish = len(signals.get("bearish", []))
        neutral = len(signals.get("neutral", []))
        snapshot.setdefault("insights", {}).update({
            "signal_bullish": bullish,
            "signal_bearish": bearish,
            "signal_neutral": neutral
        })
    if recommendations:
        snapshot.setdefault("insights", {})["recommendation_count"] = len(recommendations)
    if quote:
        snapshot.setdefault("insights", {})["last_price"] = quote.get("price") or quote.get("cur_price")

    cost = time.time() - start
    snapshot["execution_time"] = cost
    logger.info(f"[analysis.snapshot.done] code={code} cost={cost:.3f}s")
    return snapshot


@router.post("/api/analysis/multi_model",
          operation_id="run_multi_model_analysis",
          summary="多模型并行策略分析",
          tags=["analysis"])
async def run_multi_model_analysis(request: MultiModelAnalysisRequest) -> Dict[str, Any]:
    if not S._server_ready:
        raise HTTPException(status_code=503, detail="服务器正在初始化中")
    if not S.multi_model_service:
        raise HTTPException(status_code=503, detail="多模型分析服务不可用")
    snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=request.code))
    context_text = S._build_analysis_context_text(snapshot)
    result = await S.multi_model_service.run_analysis(
        code=request.code,
        models=request.models,
        judge_model=request.judge_model,
        context_text=context_text,
        context_snapshot=snapshot,
        question=request.question,
    )
    return result


@router.post(
    "/api/analysis/multi_model/model",
    operation_id="run_single_model_analysis",
    summary="单模型策略分析",
    tags=["analysis"],
)
async def run_single_model_analysis(request: SingleModelAnalysisRequest) -> Dict[str, Any]:
    if not S._server_ready or not S.multi_model_service:
        raise HTTPException(status_code=503, detail="多模型分析服务不可用")
    snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=request.code))
    context_text = S._build_analysis_context_text(snapshot)
    context_snapshot = dict(snapshot)
    context_snapshot["context_text"] = context_text
    result = await S.multi_model_service.run_single_analysis(
        code=request.code,
        model=request.model,
        context_text=context_text,
        question=request.question,
    )
    return {**result, "context_snapshot": context_snapshot}


@router.post(
    "/api/analysis/multi_model/judge",
    operation_id="run_multi_model_judge",
    summary="多模型评审整合",
    tags=["analysis"],
)
async def run_multi_model_judge(request: MultiModelJudgeRequest) -> Dict[str, Any]:
    if not S._server_ready or not S.multi_model_service:
        raise HTTPException(status_code=503, detail="多模型分析服务不可用")
    snapshot = await get_analysis_snapshot(AnalysisSnapshotRequest(code=request.code))
    context_text = S._build_analysis_context_text(snapshot)
    context_snapshot = dict(snapshot)
    context_snapshot["context_text"] = context_text
    judge = await S.multi_model_service.run_judge_only(
        code=request.code,
        judge_model=request.judge_model,
        context_text=context_text,
        base_results=request.base_results,
        question=request.question,
    )
    judge["context_snapshot"] = context_snapshot
    return judge


# ==================== 技术分析接口 ====================
@router.post("/api/analysis/technical_indicators",
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
        if S.cache_manager:
            cached_indicators = await S.cache_manager.get_indicator_data(
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
        simplified_data = S._create_simplified_response(indicators, request.code, len(kline_data))
        
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
        if S.cache_manager:
            await S.cache_manager.store_indicator_data(
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


@router.post("/api/analysis/macd",
          operation_id="get_macd_indicator",
          summary="获取MACD指标")
async def get_macd_indicator(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """单独获取MACD指标"""
    # 复用comprehensive接口但只返回MACD
    request.indicators = [IndicatorType.MACD]
    return await get_technical_indicators(request)


@router.post("/api/analysis/rsi",
          operation_id="get_rsi_indicator", 
          summary="获取RSI指标")
async def get_rsi_indicator(request: TechnicalAnalysisRequest) -> Dict[str, Any]:
    """单独获取RSI指标"""
    request.indicators = [IndicatorType.RSI]
    return await get_technical_indicators(request)
