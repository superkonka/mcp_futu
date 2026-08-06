"""基本面搜索接口 —— 从 main_enhanced.py 机械拆分，行为不变。"""
from fastapi import APIRouter

from web_api.shared import *  # noqa: F401,F403
from web_api import shared as S  # 运行期全局（服务实例 / _server_ready）
from web_api.routes.analysis import get_technical_indicators  # 跨模块复用（原单文件内直接调用）

router = APIRouter()




# ==================== 基本面搜索接口 ====================

@router.post("/api/fundamental/search",
          operation_id="get_fundamental_search",
          summary="🔍 基本面信息搜索",
          description="通过metaso搜索API获取股票相关基本面信息、新闻和分析")
async def get_fundamental_search(request: FundamentalSearchRequest) -> APIResponse:
    """基本面信息搜索"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用基本面搜索功能", data=None)
    
    try:
        # 调用基本面搜索服务
        result = await fundamental_service.search_fundamental_info(request)
        return APIResponse(
            ret_code=0,
            ret_msg="基本面搜索成功",
            data=result.dict()
        )
    except Exception as e:
        logger.error(f"基本面搜索失败: {e}")
        error_msg = str(e)
        if "网络" in error_msg or "连接" in error_msg:
            error_msg = "搜索服务网络连接失败，请稍后重试"
        elif "权限" in error_msg or "授权" in error_msg:
            error_msg = "搜索服务权限验证失败"
        elif "超时" in error_msg:
            error_msg = "搜索请求超时，请稍后重试"
        
        return APIResponse(ret_code=-1, ret_msg=f"基本面搜索失败: {error_msg}", data=None)


@router.post("/api/fundamental/stock_search",
          operation_id="get_stock_fundamental",
          summary="🔍 股票基本面搜索",
          description="搜索特定股票的基本面信息，自动构建搜索关键词")
async def get_stock_fundamental(request: dict) -> APIResponse:
    """股票基本面搜索 - 简化接口"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用基本面搜索功能", data=None)
    
    try:
        stock_code = request.get("stock_code", "")
        stock_name = request.get("stock_name", "")
        
        if not stock_code:
            return APIResponse(ret_code=-1, ret_msg="股票代码不能为空", data=None)
        
        # 调用股票基本面搜索服务
        return await fundamental_service.search_stock_fundamental(stock_code, stock_name)
        
    except Exception as e:
        logger.error(f"股票基本面搜索失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"股票基本面搜索失败: {str(e)}", data=None)


@router.post("/api/fundamental/news/refresh",
          operation_id="refresh_fundamental_news",
          summary="刷新基本面资讯",
          description="根据指定数量重新抓取 Metaso 资讯并更新本地存储")
async def refresh_fundamental_news(request: FundamentalNewsRefreshRequest) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用基本面搜索功能", data=None)
    try:
        start_ts = time.time()
        logger.info(
            "[fundamental.refresh.start] code=%s size=%s days=%s",
            request.code,
            request.size,
            request.days,
        )
        signals = await S._fetch_news_signals(
            request.code,
            request.size,
            days=request.days,
            stock_name=request.stock_name,
        )
        elapsed = time.time() - start_ts
        bull_len = len(signals.get("bullish", [])) if signals else 0
        bear_len = len(signals.get("bearish", [])) if signals else 0
        neutral_len = len(signals.get("neutral", [])) if signals else 0
        logger.info(
            "[fundamental.refresh.done] code=%s size=%s days=%s cost=%.3fs bullish=%s bearish=%s neutral=%s",
            request.code,
            request.size,
            request.days,
            elapsed,
            bull_len,
            bear_len,
            neutral_len,
        )
        return APIResponse(ret_code=0, ret_msg="刷新成功", data={"signals": signals})
    except Exception as e:
        logger.error(f"刷新基本面资讯失败: {e}")
        return APIResponse(ret_code=-1, ret_msg=f"刷新基本面资讯失败: {e}", data=None)


@router.get("/api/fundamental/summary",
         operation_id="get_fundamental_summary",
         summary="获取本地基本面汇总",
         description="从本地缓存的资讯中构建简要汇总，不触发外部搜索")
async def get_fundamental_summary(code: str, limit: int = 12) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用基本面功能", data=None)
    try:
        signals = await S._fetch_news_signals(code, size=limit, refresh=False)
        summary = (signals or {}).get("summary") or {}
        return APIResponse(ret_code=0, ret_msg="ok", data={"summary": summary})
    except Exception as exc:
        logger.error(f"获取基本面汇总失败: {exc}")
        return APIResponse(ret_code=-1, ret_msg=f"获取基本面汇总失败: {exc}", data=None)


@router.post("/api/fundamental/reports",
          operation_id="list_fundamental_reports",
          summary="列出基本面报告",
          description="按代码/period分页读取已生成的基本面报告")
async def list_fundamental_reports(request: FundamentalReportListRequest) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.fundamental_storage:
        return APIResponse(ret_code=-1, ret_msg="本地存储不可用", data=None)
    try:
        reports = S.fundamental_storage.list_reports(request.code, period=request.period, limit=request.limit, offset=request.offset)
        return APIResponse(ret_code=0, ret_msg="ok", data={"items": reports})
    except Exception as exc:
        logger.error(f"列出基本面报告失败: {exc}")
        return APIResponse(ret_code=-1, ret_msg=f"列出基本面报告失败: {exc}", data=None)


@router.post("/api/fundamental/news/search_custom",
          operation_id="search_fundamental_news_custom",
          summary="自定义关键词新闻搜索（Metaso直查）",
          description="用户输入关键词直接调用Metaso搜索，不使用股票代码拼接")
async def search_fundamental_news_custom(request: CustomFundamentalNewsSearchRequest) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 未配置", data=None)
    try:
        fs_req = FundamentalSearchRequest(
            q=request.q,
            scope="webpage",
            includeSummary=True,
            size=request.size,
            includeRawContent=False,
            conciseSnippet=True
        )
        resp = await fundamental_service.search_fundamental_info(fs_req)
        return APIResponse(ret_code=0, ret_msg="ok", data=resp.dict())
    except Exception as exc:
        logger.error(f"自定义新闻搜索失败: {exc}")
        return APIResponse(ret_code=-1, ret_msg=f"搜索失败: {exc}", data=None)


@router.get("/api/fundamental/report/{report_id}",
         operation_id="get_fundamental_report",
         summary="获取单条基础面报告详情")
async def get_fundamental_report(report_id: int) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.fundamental_storage:
        return APIResponse(ret_code=-1, ret_msg="本地存储不可用", data=None)
    try:
        report = S.fundamental_storage.get_report_by_id(report_id)
        if not report:
            return APIResponse(ret_code=-1, ret_msg="报告不存在", data=None)
        meta = report.get("meta") or {}
        refs = meta.get("references") or []
        has_tech = any((ref.get("source") or "") == "technical" for ref in refs)
        if not refs:
            refs = []
        if not refs:
            # 旧数据兜底：按报告 days/size_limit 重新从本地库构造引用点，避免前端无可选引用
            try:
                days = int(report.get("days") or 3)
                limit = int(report.get("size_limit") or 30)
                records = S.fundamental_storage.get_news_since(report.get("code", ""), days=days, limit=limit)
                for idx, rec in enumerate(records):
                    analysis = rec.get("analysis") or {}
                    title = rec.get("title") or "未命名资讯"
                    sentiment = analysis.get("sentiment") or rec.get("sentiment") or "中性"
                    summary = analysis.get("summary") or rec.get("snippet") or ""
                    date = rec.get("publish_time") or rec.get("published_at") or rec.get("last_seen") or ""
                    ref_id = rec.get("unique_key") or rec.get("url") or f"ref-{idx+1}"
                    refs.append({
                        "id": idx + 1,
                        "ref_id": ref_id,
                        "unique_key": rec.get("unique_key"),
                        "title": title,
                        "publish_time": date,
                        "source": rec.get("source"),
                        "url": rec.get("url"),
                        "sentiment": sentiment,
                        "summary": summary,
                    })
            except Exception as _build_exc:
                logger.warning(f"报告引用构造失败: { _build_exc }")
        if not has_tech:
            try:
                tech_req = TechnicalAnalysisRequest(
                    code=report.get("code", ""),
                    indicators=[IndicatorType.MACD, IndicatorType.RSI, IndicatorType.MA],
                    ktype="K_DAY",
                    period=180
                )
                tech_resp = await get_technical_indicators(tech_req)
                if isinstance(tech_resp, dict) and tech_resp.get("ret_code") == 0:
                    tdata = tech_resp.get("data") or {}
                    summary = tdata.get("summary") or tdata.get("overall_view") or tdata.get("signal_summary")
                    if not summary:
                        signals = tdata.get("signals") or {}
                        if signals:
                            summary = "; ".join(f"{k}:{v}" for k, v in signals.items())
                    if summary:
                        refs.append({
                            "id": "tech-summary",
                            "ref_id": "technical-summary",
                            "title": "技术面摘要",
                            "publish_time": datetime.now(timezone.utc).isoformat(),
                            "source": "technical",
                            "sentiment": "技术",
                            "summary": summary,
                        })
            except Exception as tech_exc:
                logger.warning(f"报告引用构造技术面失败: {tech_exc}")
        meta["references"] = refs
        report["meta"] = meta
        return APIResponse(ret_code=0, ret_msg="ok", data={"report": report})
    except Exception as exc:
        logger.error(f"获取报告失败: {exc}")
        return APIResponse(ret_code=-1, ret_msg=f"获取报告失败: {exc}", data=None)


@router.post("/api/fundamental/report/chat",
          operation_id="chat_with_fundamental_report",
          summary="基于基础面报告进行对话",
          description="将报告正文作为上下文，使用 DeepSeek 回答附加问题")
async def chat_with_fundamental_report(request: FundamentalReportChatRequest) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.deepseek_service or not S.deepseek_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="DeepSeek 未配置，无法对话", data=None)
    if not S.fundamental_storage:
        return APIResponse(ret_code=-1, ret_msg="本地存储不可用", data=None)
    try:
        report = S.fundamental_storage.get_report_by_id(request.report_id)
        if not report:
            return APIResponse(ret_code=-1, ret_msg="报告不存在", data=None)
        selected_refs: List[Dict[str, Any]] = []
        report_meta = report.get("meta") or {}
        meta_refs = report_meta.get("references") or []
        if request.references:
            selected_refs = request.references[:8]
        elif request.ref_ids:
            ref_id_set = set([str(rid) for rid in request.ref_ids])
            for r in meta_refs:
                rid = str(r.get("ref_id") or r.get("unique_key") or r.get("id") or "")
                if rid and rid in ref_id_set:
                    selected_refs.append(r)
            selected_refs = selected_refs[:8]
        # 构造上下文
        system_prompt = (
            "你是一名研究员，基于提供的基础面报告回答追加问题。保持简洁，直接引用报告要点，不要虚构。"
        )
        extra_context = ""
        if selected_refs:
            lines = []
            for idx, ref in enumerate(selected_refs):
                title = ref.get("title") or "未命名资讯"
                date = ref.get("publish_time") or ref.get("published_at") or ref.get("last_seen") or ""
                source = ref.get("source") or ""
                summary = ref.get("summary") or ""
                sentiment = ref.get("sentiment") or ""
                lines.append(f"{idx+1}. [{date}] {source} {sentiment} 标题:{title} 摘要:{summary}")
            extra_context = "附加上下文（选中的引用点）：\n" + "\n".join(lines)

        user_prompt = f"报告摘要:\n{report.get('report')}\n\n{extra_context}\n\n问题: {request.question}\n请用中文回答，条理清晰，限制在300字以内。"
        reply = await S.deepseek_service.chat(system_prompt, user_prompt, temperature=0.2)
        if not reply:
            return APIResponse(ret_code=-1, ret_msg="DeepSeek 未返回内容", data=None)
        return APIResponse(ret_code=0, ret_msg="ok", data={"answer": reply.strip()})
    except Exception as exc:
        logger.error(f"报告对话失败: {exc}")
        return APIResponse(ret_code=-1, ret_msg=f"报告对话失败: {exc}", data=None)


@router.post("/api/fundamental/report",
          operation_id="build_fundamental_report",
          summary="对最近N天的资讯做DeepSeek汇总，生成基本面报告",
          description="读取本地缓存资讯，按天数过滤后汇总，调用DeepSeek生成摘要报告，避免逐条分析过长token")
async def build_fundamental_report(request: Dict[str, Any]) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.deepseek_service or not S.deepseek_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="DeepSeek 未配置，无法生成报告", data=None)
    if not S.fundamental_storage:
        return APIResponse(ret_code=-1, ret_msg="本地存储不可用", data=None)
    code = request.get("code") or ""
    stock_name = request.get("stock_name") or ""
    period = (request.get("period") or "daily").lower()
    date_str = request.get("date")
    days = int(request.get("days") or (7 if period == "weekly" else 3))
    limit = int(request.get("limit") or 30)
    source = request.get("source") or "manual"
    if not date_str:
        today = datetime.now(timezone.utc).date()
        if period == "weekly":
            monday = today - timedelta(days=today.weekday())
            date_str = monday.isoformat()
        else:
            date_str = today.isoformat()
    try:
        records = S.fundamental_storage.get_news_since(code, days=days, limit=limit)
        if not records:
            return APIResponse(ret_code=-1, ret_msg="无可用资讯用于汇总", data=None)
        references = []
        tech_reference = None
        try:
            tech_req = TechnicalAnalysisRequest(
                code=code,
                indicators=[IndicatorType.MACD, IndicatorType.RSI, IndicatorType.MA],
                ktype="K_DAY",
                period=180
            )
            tech_resp = await get_technical_indicators(tech_req)
            if isinstance(tech_resp, dict) and tech_resp.get("ret_code") == 0:
                tdata = tech_resp.get("data") or {}
                summary = tdata.get("summary") or tdata.get("overall_view") or tdata.get("signal_summary")
                if not summary:
                    signals = tdata.get("signals") or {}
                    if signals:
                        summary = "; ".join(f"{k}:{v}" for k, v in signals.items())
                if summary:
                    tech_reference = {
                        "id": "tech-summary",
                        "ref_id": "technical-summary",
                        "title": "技术面摘要",
                        "publish_time": datetime.now(timezone.utc).isoformat(),
                        "source": "technical",
                        "sentiment": "技术",
                        "summary": summary,
                    }
        except Exception as tech_exc:
            logger.warning(f"构造技术面引用失败: {tech_exc}")
        lines = []
        for idx, rec in enumerate(records):
            analysis = rec.get("analysis") or {}
            title = rec.get("title") or "未命名资讯"
            sentiment = analysis.get("sentiment") or rec.get("sentiment") or "中性"
            summary = analysis.get("summary") or rec.get("snippet") or ""
            date = rec.get("publish_time") or rec.get("published_at") or rec.get("last_seen") or ""
            ref_id = rec.get("unique_key") or rec.get("url") or f"ref-{idx+1}"
            references.append({
                "id": idx + 1,
                "ref_id": ref_id,
                "unique_key": rec.get("unique_key"),
                "title": title,
                "publish_time": date,
                "source": rec.get("source"),
                "url": rec.get("url"),
                "sentiment": sentiment,
                "summary": summary,
            })
            lines.append(f"{idx+1}. [{date}] 情绪:{sentiment} 标题:{title} 来源:{rec.get('source') or ''} 摘要:{summary}")
        user_prompt = (
            f"请基于以下{len(lines)}条资讯（近{days}天内，本地缓存，已按时间排序），生成一份不超过500字的基本面摘要报告，"
            "需包含：整体情绪、核心利好/利空因素、风险提示、时间敏感点，最后给一个一句话结论。"
            "只输出报告正文，不要JSON，不要逐条重复全文。\n\n"
            + "\n".join(lines)
        )
        system_prompt = "你是资深卖方分析师，擅长压缩资讯为简短要点，避免冗长重复。"
        content = await S.deepseek_service.chat(system_prompt, user_prompt, temperature=0.2)
        if not content:
            return APIResponse(ret_code=-1, ret_msg="DeepSeek 未返回内容", data=None)
        report_text = content.strip()
        response_references = references + ([tech_reference] if tech_reference else [])
        # 存库
        try:
            meta = {
                "counts": len(lines),
                "days": days,
                "limit": limit,
                "source": source,
                "references": response_references,
            }
            S.fundamental_storage.upsert_report({
                "code": code,
                "stock_name": stock_name,
                "period": period,
                "date": date_str,
                "title": f"{code} {date_str} { '周报' if period == 'weekly' else '日报'}",
                "report": report_text,
                "items_used": len(lines),
                "days": days,
                "size_limit": limit,
                "source": source,
                "meta": meta,
            })
        except Exception as store_exc:
            logger.warning(f"报告存储失败: {store_exc}")
        return APIResponse(
            ret_code=0,
            ret_msg="ok",
            data={
                "report": report_text,
                "items_used": len(lines),
                "days": days,
                "limit": limit,
                "period": period,
                "date": date_str,
                "references": response_references,
            },
        )
    except Exception as exc:
        logger.error(f"生成基本面报告失败: {exc}")
        return APIResponse(ret_code=-1, ret_msg=f"生成基本面报告失败: {exc}", data=None)


@router.post("/api/fundamental/news/list",
          operation_id="list_fundamental_news",
          summary="列出本地已存的基本面资讯",
          description="仅访问本地DB，支持状态/日期过滤，不访问外部搜索")
async def list_fundamental_news(request: FundamentalNewsListRequest) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.fundamental_storage:
        return APIResponse(ret_code=-1, ret_msg="本地存储不可用", data=None)
    try:
        items = S.fundamental_storage.list_news(
            code=request.code,
            status=request.status,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit,
            offset=request.offset,
        )
        return APIResponse(ret_code=0, ret_msg="ok", data={"items": items})
    except Exception as exc:
        logger.error(f"列出基本面资讯失败: {exc}")
        return APIResponse(ret_code=-1, ret_msg=f"列出基本面资讯失败: {exc}", data=None)


@router.post("/api/fundamental/analyze_now",
          operation_id="analyze_fundamental_now",
          summary="触发单条资讯即时分析",
          description="对指定资讯立即调用 DeepSeek 分析并更新入库")
async def analyze_fundamental_now(request: dict) -> APIResponse:
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not S.deepseek_service or not S.deepseek_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="DeepSeek 未配置，无法分析", data=None)
    if not S.fundamental_storage:
        return APIResponse(ret_code=-1, ret_msg="本地存储不可用", data=None)
    code = request.get("code") or ""
    title = request.get("title") or ""
    url = request.get("url") or ""
    publish_time = request.get("publish_time") or request.get("published_at")
    payload = {
        "code": code,
        "title": title,
        "url": url,
        "source": request.get("source"),
        "snippet": request.get("snippet"),
        "publish_time": publish_time,
    }
    try:
        analysis = await S.deepseek_service.analyze_fundamental_news(payload)
        if analysis is None:
            # 视为失败并入库标记，便于前端看到“分析失败/待重试”
            unique_key = S.fundamental_storage.make_unique_key(code, title, url, publish_time)
            fail_record = {
                "code": code,
                "title": title,
                "url": url,
                "snippet": request.get("snippet"),
                "publish_time": publish_time,
                "analysis": {
                    "analysis_provider": "fail",
                    "analysis_error": S.deepseek_service.last_error_message or "未返回结果",
                    "sentiment": request.get("sentiment"),
                },
                "unique_key": unique_key,
                "needs_reanalysis": 1,
            }
            S.fundamental_storage.upsert(fail_record)
            return APIResponse(ret_code=-1, ret_msg=S.deepseek_service.last_error_message or "分析失败，未返回结果", data=None)
        analysis["analysis_provider"] = "deepseek"
        unique_key = S.fundamental_storage.make_unique_key(code, title, url, publish_time)
        stored = S.fundamental_storage.get_by_unique_key(unique_key) or {}
        record = {**stored, **payload, "analysis": analysis, "unique_key": unique_key}
        record["needs_reanalysis"] = 0
        S.fundamental_storage.upsert(record)
        logger.info("[fundamental.analyze_now] code=%s title=%s provider=deepseek", code, title)
        return APIResponse(ret_code=0, ret_msg="分析完成", data={"analysis": analysis})
    except Exception as exc:
        logger.error(f"即时分析失败: {exc}")
        # 标记为失败，后续可重试
        try:
            unique_key = S.fundamental_storage.make_unique_key(code, title, url, publish_time)
            record = {
                "code": code,
                "title": title,
                "url": url,
                "snippet": request.get("snippet"),
                "publish_time": publish_time,
                "analysis": {
                    "analysis_provider": "fail",
                    "analysis_error": str(exc),
                    "sentiment": request.get("sentiment"),
                },
                "unique_key": unique_key,
                "needs_reanalysis": 1,
            }
            S.fundamental_storage.upsert(record)
        except Exception:
            pass
        return APIResponse(ret_code=-1, ret_msg=f"分析失败: {exc}", data=None)


@router.post("/api/fundamental/read_webpage",
          operation_id="read_webpage",
          summary="📄 读取网页内容",
          description="通过metaso reader API读取任意网页的纯文本内容")
async def read_webpage_endpoint(request: dict) -> APIResponse:
    """读取网页内容"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用网页读取功能", data=None)
    
    try:
        url = request.get("url", "")
        if not url:
            return APIResponse(ret_code=-1, ret_msg="网页URL不能为空", data=None)
        
        # 调用网页读取服务
        content = await fundamental_service.read_webpage(url)
        
        return APIResponse(
            ret_code=0,
            ret_msg="网页读取成功",
            data={
                "url": url,
                "content": content,
                "content_length": len(content),
                "api_source": "metaso"
            }
        )
        
    except Exception as e:
        logger.error(f"网页读取失败: {e}")
        error_msg = str(e)
        if "网络" in error_msg or "连接" in error_msg:
            error_msg = "网页读取网络连接失败，请稍后重试"
        elif "404" in error_msg:
            error_msg = "网页不存在或无法访问"
        elif "超时" in error_msg:
            error_msg = "网页读取超时，请稍后重试"
        
        return APIResponse(ret_code=-1, ret_msg=f"网页读取失败: {error_msg}", data=None)


@router.post("/api/fundamental/chat",
          operation_id="chat_completion",
          summary="💬 智能问答",
          description="通过metaso chat API进行智能问答对话")
async def chat_endpoint(request: dict) -> APIResponse:
    """智能问答"""
    if not S._server_ready:
        return APIResponse(ret_code=-1, ret_msg="服务器正在初始化中，请稍后重试", data=None)
    if not fundamental_service.is_configured():
        return APIResponse(ret_code=-1, ret_msg="Metaso API 密钥未配置，无法使用智能问答功能", data=None)
    
    try:
        messages = request.get("messages", [])
        model = request.get("model", "fast")
        stream = request.get("stream", True)
        
        if not messages:
            return APIResponse(ret_code=-1, ret_msg="对话消息不能为空", data=None)
        
        # 转换消息格式
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            else:
                formatted_messages.append({
                    "role": "user",
                    "content": str(msg)
                })
        
        # 调用问答服务
        answer = await fundamental_service.chat_completion(formatted_messages, model, stream)
        
        return APIResponse(
            ret_code=0,
            ret_msg="问答成功",
            data={
                "answer": answer,
                "model": model,
                "stream": stream,
                "messages": formatted_messages,
                "api_source": "metaso"
            }
        )
        
    except Exception as e:
        logger.error(f"问答失败: {e}")
        error_msg = str(e)
        if "网络" in error_msg or "连接" in error_msg:
            error_msg = "问答服务网络连接失败，请稍后重试"
        elif "权限" in error_msg or "授权" in error_msg:
            error_msg = "问答服务权限验证失败"
        elif "超时" in error_msg:
            error_msg = "问答请求超时，请稍后重试"
        
        return APIResponse(ret_code=-1, ret_msg=f"问答失败: {error_msg}", data=None)
