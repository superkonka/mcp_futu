"""web_api 共享层：原 main_enhanced.py 的导入、全局状态、请求模型与辅助函数。

服务实例由 main_enhanced.lifespan 在启动时赋到本模块属性上，
路由模块通过 `from web_api import shared as S` 访问，保证读到的是运行期值。
"""

import asyncio
import time
import secrets
import json
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone, time as dtime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from collections import defaultdict
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as log  # Use alias to avoid conflicts
from contextlib import asynccontextmanager
from futu import *
from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# 导入原有模块
from services.futu_service import FutuService
from models.futu_models import *
from models.analysis_models import *
from config import settings

# 导入新功能模块  
from cache.cache_manager import DataCacheManager, CacheConfig
from analysis.technical_indicators import TechnicalIndicators, TechnicalData, IndicatorConfig
from models.fundamental_models import FundamentalSearchRequest
from models.fundamental_models import FundamentalSearchRequest
# 导入基本面搜索服务
from services.fundamental_service import fundamental_service
from models.fundamental_models import FundamentalSearchRequest, FundamentalSearchResponse
from services.recommendation_storage import RecommendationStorageService
from models.recommendation_models import RecommendationWriteRequest, RecommendationQueryRequest, RecommendationUpdateRequest, RecommendationReevaluateRequest
from models.dashboard_models import DashboardSessionRequest, DashboardSessionResponse, DashboardSessionItem
from services.dashboard_stream import DashboardStreamManager
from services.dashboard_session_store import DashboardSessionStore
from services.deepseek_service import DeepSeekService
from services.fundamental_storage import FundamentalNewsStorage
from services.minute_kline_storage import MinuteKlineStorage
from services.multi_model_service import MultiModelAnalysisService
from services.strategy_monitor import StrategyMonitorService


# Ensure we use loguru logger after futu import
logger = log

# 全局变量
futu_service: Optional[FutuService] = None
cache_manager: Optional[DataCacheManager] = None
recommendation_storage: Optional[RecommendationStorageService] = None
deepseek_service: Optional[DeepSeekService] = None
fundamental_storage: Optional[FundamentalNewsStorage] = None
_server_ready = False
dashboard_sessions: Dict[str, Dict[str, Any]] = {}
_dashboard_lock = asyncio.Lock()
dashboard_stream_manager: Optional[DashboardStreamManager] = None
dashboard_session_store: Optional[DashboardSessionStore] = None
minute_kline_storage: Optional[MinuteKlineStorage] = None
multi_model_service: Optional[MultiModelAnalysisService] = None
strategy_monitor: Optional[StrategyMonitorService] = None
DASHBOARD_DIST_PATH = Path("web/dashboard-app/dist")


class MultiModelAnalysisRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    models: List[str] = Field(default_factory=lambda: ["deepseek", "kimi"], description="参与分析的模型列表")
    judge_model: str = Field("gemini", description="最终评审模型")
    question: Optional[str] = Field(None, description="额外关注的问题")


class SingleModelAnalysisRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    model: str = Field(..., description="需要调用的模型: deepseek/kimi/gemini")
    question: Optional[str] = Field(None, description="额外问题")


class MultiModelJudgeRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    judge_model: str = Field("gemini", description="评审模型, 例如 gemini/deepseek")
    base_results: List[Dict[str, Any]] = Field(..., description="各模型的原始结果")
    question: Optional[str] = Field(None, description="额外问题")


class FundamentalNewsRefreshRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    size: int = Field(10, ge=10, le=100, description="Metaso 搜索数量")
    days: int = Field(3, ge=1, le=30, description="限定最近N天的资讯，默认3天")
    stock_name: Optional[str] = Field(None, description="股票名称（可选，优先用于搜索关键词）")

class FundamentalNewsListRequest(BaseModel):
    code: Optional[str] = Field(None, description="股票代码")
    status: Optional[str] = Field(None, description="pending/fail/done")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)

class FundamentalReportListRequest(BaseModel):
    code: str = Field(..., description="股票代码, 如 HK.00700")
    period: Optional[str] = Field(None, description="daily/weekly")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

class FundamentalReportChatRequest(BaseModel):
    report_id: int
    question: str
    ref_ids: Optional[List[str]] = Field(None, description="可选，引用点ID列表（与报告meta.references中的ref_id/unique_key匹配）")
    references: Optional[List[Dict[str, Any]]] = Field(None, description="可选，直接传递的引用点内容")

class CustomFundamentalNewsSearchRequest(BaseModel):
    q: str = Field(..., description="自定义搜索关键词")
    size: int = Field(10, ge=1, le=50, description="返回数量，默认10，最多50")


def _get_next_trading_day(current_time: datetime) -> datetime:
    """计算下一个交易日"""
    next_day = current_time + timedelta(days=1)
    
    # 跳过周末
    while next_day.weekday() >= 5:  # 周六=5, 周日=6
        next_day += timedelta(days=1)
    
    return next_day


async def _persist_dashboard_sessions():
    if not dashboard_session_store:
        return
    snapshot = {}
    async with _dashboard_lock:
        for session_id, info in dashboard_sessions.items():
            snapshot[session_id] = {
                "code": info.get("code"),
                "nickname": info.get("nickname"),
                "created_at": info.get("created_at")
            }
    await asyncio.to_thread(dashboard_session_store.save, snapshot)


def _remove_duplicate_sessions_locked() -> List[Tuple[str, str]]:
    """必须在持有_dashboard_lock时调用，按code去重并返回移除记录(session_id, code)"""
    seen_codes = set()
    duplicates: List[Tuple[str, str]] = []
    for session_id, info in list(dashboard_sessions.items()):
        code = info.get("code")
        if not code:
            continue
        if code in seen_codes:
            duplicates.append((session_id, code))
            dashboard_sessions.pop(session_id, None)
        else:
            seen_codes.add(code)
    return duplicates


def _get_session_window(code: str) -> Dict[str, Any]:
    market = "HK" if code.upper().startswith("HK.") else "US"
    tz_offset = 8 if market == "HK" else -5
    tz = timezone(timedelta(hours=tz_offset))
    today_local = datetime.now(tz).date()

    def local_iso(hour: int, minute: int) -> str:
        dt = datetime.combine(today_local, dtime(hour=hour, minute=minute, tzinfo=tz))
        return dt.astimezone(timezone.utc).isoformat()

    if market == "HK":
        window = {
            "market": "HK",
            "open_time": local_iso(9, 30),
            "break_start": local_iso(12, 0),
            "break_end": local_iso(13, 0),
            "close_time": local_iso(16, 0),
        }
    else:
        window = {
            "market": market,
            "open_time": local_iso(9, 30),
            "close_time": local_iso(16, 0),
        }
    return window


BULLISH_KEYWORDS = ["上涨", "利好", "增持", "创新高", "超预期", "大幅增长", "获批", "回购", "上调"]
BULLISH_KEYWORDS = [...]
BULLISH_KEYWORDS = ["上涨", "利好", "增持", "创新高", "超预期", "大幅增长", "获批", "回购", "上调"]
BEARISH_KEYWORDS = ["下跌", "利空", "警告", "亏损", "裁员", "大幅减少", "下调", "减持", "停牌"]


def _normalize_datetime(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_publish_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 1_000_000_000_000:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            return _normalize_datetime(datetime.fromisoformat(raw))
        except Exception:
            pass
        try:
            dt = parsedate_to_datetime(raw)
            return _normalize_datetime(dt)
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return _normalize_datetime(dt)
            except Exception:
                continue
    return None


def _ensure_dashboard_session(session_id: str) -> Dict[str, Any]:
    session = dashboard_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="dashboard session not found")
    return session


async def _fetch_quote_snapshot(code: str) -> Optional[Dict[str, Any]]:
    if not futu_service:
        logger.warning(f"[quote.snapshot] futu_service_unavailable code={code}")
        return None
    request = StockQuoteRequest(code_list=[code])
    result = await futu_service.get_stock_quote(request)
    if result.ret_code != 0 or not result.data:
        logger.warning(f"[quote.snapshot] ret={result.ret_code} empty={not bool(result.data)} code={code}")
        return None
    quotes = result.data.get("quotes") or []
    if not quotes:
        logger.warning(f"[quote.snapshot] no_quotes code={code}")
        return None
    raw = quotes[0]

    def _to_float(value: Any) -> Optional[float]:
        if value in ("", None):
            return None
        if isinstance(value, (int, float)):
            try:
                as_float = float(value)
                if as_float != as_float:  # NaN
                    return None
                return as_float
            except (TypeError, ValueError):
                return None
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned or cleaned in {"--", "N/A", "null", "-"}:
                return None
            cleaned = cleaned.replace(",", "")
            try:
                if cleaned.endswith("%"):
                    cleaned = cleaned.rstrip("%")
                return float(cleaned)
            except ValueError:
                return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    try:
        last_price = _to_float(raw.get("last_price") or raw.get("price"))
        prev_close = _to_float(raw.get("prev_close_price") or raw.get("prev_close"))
        change_rate = _to_float(raw.get("change_rate"))
        open_price = _to_float(raw.get("open_price") or raw.get("open"))
        high_price = _to_float(raw.get("high_price") or raw.get("high"))
        low_price = _to_float(raw.get("low_price") or raw.get("low"))
        volume = _to_float(raw.get("volume"))
        turnover = _to_float(raw.get("turnover"))
        change_value = None
        if last_price is not None and prev_close is not None:
            change_value = last_price - prev_close
            if (change_rate is None or change_rate == 0) and prev_close:
                try:
                    change_rate = (change_value / prev_close) * 100
                except ZeroDivisionError:
                    change_rate = None
        return {
            "code": raw.get("code"),
            "name": raw.get("stock_name") or raw.get("name"),
            "price": last_price,
            "last_price": last_price,
            "change_rate": change_rate,
            "change_value": change_value,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "prev_close": prev_close,
            "volume": volume,
            "turnover": turnover,
            "update_time": raw.get("update_time")
        }
    except Exception:
        return raw


async def _fetch_recommendations_snapshot(code: str) -> List[Dict[str, Any]]:
    if not recommendation_storage:
        return []
    req = RecommendationQueryRequest(code=code, limit=5)
    return await asyncio.to_thread(recommendation_storage.get_recommendations, req.dict())


async def _fetch_holding_snapshot(code: str) -> Optional[Dict[str, Any]]:
    if not futu_service or not futu_service.has_trade_connection():
        return None
    try:
        request = PositionListRequest(code=code, trd_env=TrdEnv.REAL)
        result = await futu_service.get_position_list(request)
        if result.ret_code != 0 or not result.data:
            return None
        positions = result.data.get("position_list") or []
        if not positions:
            return None
        pos = positions[0]
        qty = float(pos.get("qty") or 0)
        cost_price = float(pos.get("cost_price") or 0)
        last_price = pos.get("price") or pos.get("last_price")
        if last_price in (None, "", 0) and futu_service:
            quote = await _fetch_quote_snapshot(code)
            if quote and quote.get("price") is not None:
                last_price = quote["price"]
        last_price = float(last_price or 0)
        pl_val = float(pos.get("pl_val") or 0)
        pl_ratio = float(pos.get("pl_ratio") or 0)  # already percent
        return {
            "持仓": qty,
            "成本": cost_price,
            "现价": last_price,
            "盈亏": pl_val,
            "盈亏比例": pl_ratio,
        }
    except Exception as exc:
        logger.debug(f"获取持仓失败: {exc}")
        return None


async def _fetch_news_signals(
    code: str,
    size: int = 12,
    refresh: bool = True,
    days: int = 3,
    stock_name: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    signals = {"bullish": [], "bearish": [], "neutral": [], "sector_news": [], "macro_news": []}
    run_remote = refresh and fundamental_service.is_configured()
    days = max(1, min(int(days or 3), 30))
    now_utc = datetime.now(timezone.utc)
    # 仅用于查询关键词的时间范围提示，不再用于过滤入库结果
    cutoff_dt = None
    max_dt = None
    refreshed_direct_records: List[Dict[str, Any]] = []
    inline_analysis = False  # 先入库，分析放后台重算

    def _normalize_publish_time(value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1e12:
                ts = ts / 1000.0
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                return None
        text = str(value).strip()
        if not text:
            return None
        lower = text.lower()
        # 相对时间处理
        if lower in {"刚刚", "刚才", "just now", "now"}:
            return now_utc.isoformat()
        rel_match = re.match(r"(\d+)\s*(分钟|分|小时|天|日)\s*前?$", text)
        if rel_match:
            amount = int(rel_match.group(1))
            unit = rel_match.group(2)
            delta_kwargs = {}
            if unit in {"分钟", "分"}:
                delta_kwargs["minutes"] = amount
            elif unit in {"小时"}:
                delta_kwargs["hours"] = amount
            elif unit in {"天", "日"}:
                delta_kwargs["days"] = amount
            if delta_kwargs:
                return (now_utc - timedelta(**delta_kwargs)).isoformat()
        if lower in {"昨天", "yesterday"}:
            return (now_utc - timedelta(days=1)).isoformat()
        # 直接解析时间戳/日期
        try:
            parsed = parsedate_to_datetime(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d"):
            try:
                dt = datetime.strptime(text, fmt)
                if fmt in ("%m-%d", "%m/%d"):
                    dt = dt.replace(year=now_utc.year)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                continue
        # 手工提取数字日期
        digits = re.findall(r"\d+", text)
        if len(digits) >= 3:
            year, month, day = digits[0], digits[1], digits[2]
            hour = digits[3] if len(digits) > 3 else "0"
            minute = digits[4] if len(digits) > 4 else "0"
            second = digits[5] if len(digits) > 5 else "0"
            try:
                dt = datetime(
                    int(year),
                    int(month),
                    int(day),
                    int(hour),
                    int(minute),
                    int(second),
                    tzinfo=timezone.utc
                )
                return dt.isoformat()
            except Exception:
                pass
        return None


    company_name = (stock_name or "").strip()

    async def _build_search_query() -> str:
        nonlocal company_name
        def _ensure_recent(q: str) -> str:
            text = q.lower()
            today_token = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            recency_token = f"最近{days}天"
            recent_tokens = [
                "最近", "本周", "过去", "近一周", "last 7 days", "past week", "today", "yesterday", "last week",
                recency_token.lower(), f"近{days}天", f"{days}天"
            ]
            if any(tok.lower() in text for tok in recent_tokens):
                return q
            return f"{q} {recency_token} {today_token}"

        try:
            quote_info = await _fetch_quote_snapshot(code)
            if quote_info and quote_info.get("name"):
                company_name = str(quote_info["name"])
        except Exception:
            company_name = code
        default_query = _ensure_recent(f"{company_name} 财报 业绩 政策 业务 基本面 最新")
        if not run_remote or not deepseek_service or not deepseek_service.is_configured():
            return default_query
        prompt = (
            "你是金融情报检索专家。请基于股票代码和公司名称，提供一个用于新闻搜索的简短中文关键词，"
            "聚焦基本面、财报、政策或竞争情报，不超过18个汉字。"
            '输出 JSON，如 {"query": "美团 基本面 财报"}。'
            f"\n股票代码: {code}\n公司名称: {company_name}"
        )
        try:
            raw = await deepseek_service.chat("你是资讯检索专家。", prompt, temperature=0.2)
            if raw:
                text = raw.strip().strip('`')
                if text.lower().startswith("json"):
                    text = text[4:].lstrip()
                data = json.loads(text)
                if isinstance(data, dict):
                    query = data.get("query")
                    if isinstance(query, str) and query.strip():
                        return _ensure_recent(query.strip())
        except Exception as exc:
            logger.debug(f"生成检索关键词失败: {exc}")
        return default_query

    def _build_code_tokens(symbol: str) -> List[str]:
        base = symbol.upper()
        tokens = {base}
        if "." in base:
            market, num = base.split(".", 1)
            tokens.update({num, num.lstrip("0") or num, f"{market}{num}", f"{market}{num.lstrip('0') or num}", f"{num}.{market}", f"{num.lstrip('0') or num}.{market}"})
        tokens.update({base.replace(".", ""), base.replace(".", " ")})
        return [token for token in tokens if token]

    def _build_name_tokens(name: str) -> List[str]:
        if not name:
            return []
        raw = name.strip()
        tokens = {raw, raw.replace(" ", ""), raw.replace("-", ""), raw.replace("_", "")}
        # 按常见分隔符拆分
        parts = re.split(r"[，,。；;、\s\/\-]+", raw)
        for part in parts:
            part = part.strip()
            if len(part) >= 2:
                tokens.add(part)
        # 针对带有括号/后缀的情况，保留主要部分
        if "(" in raw and ")" in raw:
            try:
                tokens.add(raw.split("(", 1)[0])
            except Exception:
                pass
        return [t for t in tokens if t]

    code_tokens = _build_code_tokens(code)
    name_tokens = _build_name_tokens(company_name or "")
    target_tokens = list({tok.upper() for tok in code_tokens} | {tok.upper() for tok in name_tokens})
    search_query = await _build_search_query()
    logger.info(
        "[fundamental.search.query] code=%s name=%s query=%s tokens=%s",
        code,
        company_name or "-",
        search_query,
        target_tokens,
    )

    def _has_target_token(record: Dict[str, Any]) -> bool:
        # 如果没有公司名 tokens，则不过滤（仅代码），避免过度丢弃
        if not name_tokens:
            return True
        title = (record.get("title") or "").upper()
        snippet = (record.get("snippet") or "").upper()
        merged = f"{title} {snippet}"
        return any(token and token in merged for token in target_tokens)

    def _classify_scope(record: Dict[str, Any], analysis: Optional[Dict[str, Any]]) -> str:
        # 优先：如果当前请求的 code 与记录的 code 一致，直接视为 direct，防止被误判为 sector/macro
        if record.get("code") and record.get("code") == code:
            return "direct"
        if analysis:
            scope = analysis.get("related_scope")
            if isinstance(scope, str):
                scope_lower = scope.lower()
                if scope_lower in {"direct", "sector", "macro"}:
                    if scope_lower == "direct" and not _has_target_token(record):
                        return "sector"
                    return scope_lower
            related_val = analysis.get("related")
            if isinstance(related_val, bool):
                if related_val and _has_target_token(record):
                    return "direct"
                if related_val:
                    return "sector"
                return "macro"
        if _has_target_token(record):
            return "direct"
        return "macro"

    def _fallback_analysis(text: str) -> Dict[str, Any]:
        lowered = text.lower()
        sentiment = "neutral"
        if any(key.lower() in lowered for key in BEARISH_KEYWORDS):
            sentiment = "bearish"
        elif any(key.lower() in lowered for key in BULLISH_KEYWORDS):
            sentiment = "bullish"
        scope = "direct" if any(token.lower() in lowered for token in target_tokens) else "macro"
        return {
            "sentiment": sentiment,
            "confidence": 0.4,
            "impact_horizon": "短期",
            "volatility_bias": "中性",
            "themes": [],
            "risk_factors": [],
            "opportunity_factors": [],
            "summary": text[:100],
            "action_hint": "",
            "related": scope == "direct",
            "related_scope": scope,
            "analysis_provider": "fallback"
        }

    async def _ensure_analysis(item: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "code": code,
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "source": item.get("source"),
            "publish_time": item.get("publish_time"),
            "url": item.get("url")
        }
        text = f"{payload['title'] or ''} {payload['snippet'] or ''}"
        analysis: Optional[Dict[str, Any]] = None
        if deepseek_service and deepseek_service.is_configured():
            try:
                analysis = await deepseek_service.analyze_fundamental_news(payload)
                if analysis is not None:
                    analysis["analysis_provider"] = "deepseek"
            except Exception as exc:
                logger.warning(
                    f"[fundamental.analysis] DeepSeek 调用失败，使用兜底分析 code={code} title={payload['title']} err={exc}"
                )
        if not analysis:
            detail = None
            if deepseek_service:
                detail = getattr(deepseek_service, "last_error_message", None)
            logger.warning(
                "[fundamental.analysis] 使用关键词兜底情绪，DeepSeek 无响应或解析失败 code=%s title=%s detail=%s",
                code,
                payload["title"],
                detail or "无",
            )
            analysis = _fallback_analysis(text)
            analysis["analysis_provider"] = "fallback"
        return analysis

    async def _repair_existing_records(quota: int = 5):
        if not fundamental_storage or not deepseek_service or not deepseek_service.is_configured():
            return
        pending_items = fundamental_storage.get_reanalysis_queue(code, limit=quota)
        if not pending_items:
            return
        logger.info(f"[fundamental.repair] code={code} pending={len(pending_items)} 触发重算")
        for pending in pending_items:
            try:
                analysis = await _ensure_analysis(pending)
                pending["analysis"] = analysis
                fundamental_storage.upsert(pending)
            except Exception as exc:
                logger.warning(f"[fundamental.repair] 重算失败 code={code} title={pending.get('title')} err={exc}")

    try:
        request = FundamentalSearchRequest(
            q=search_query,
            scope="news",
            includeSummary=True,
            size=min(max(size, 10), 100),
            includeRawContent=False,
            conciseSnippet=True
        )
        response = await fundamental_service.search_fundamental_info(request)
        results = response.results or []
        fetched_count = len(results)
        kept_count = 0
        new_count = 0
        updated_count = 0
        skipped_no_time = 0
        skipped_cutoff = 0
        new_items_log: List[Tuple[str, str]] = []
        updated_items_log: List[Tuple[str, str]] = []
        cutoff_items_log: List[Tuple[str, str]] = []
        notime_items_log: List[str] = []
        max_items = min(len(results), size)
        refreshed_direct_records: List[Dict[str, Any]] = []
        for item in results[:max_items]:
            raw_publish_time = item.publish_time
            normalized_publish_time = _normalize_publish_time(raw_publish_time)
            record = {
                "code": code,
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "snippet": item.snippet,
                "raw_publish_time": raw_publish_time,
                "publish_time": normalized_publish_time or raw_publish_time or now_utc.isoformat(),
            }
            unique_key = None
            stored = None
            if fundamental_storage:
                unique_key = fundamental_storage.make_unique_key(
                    code,
                    item.title or "",
                    item.url or "",
                    normalized_publish_time or raw_publish_time
                )
                stored = fundamental_storage.get_by_unique_key(unique_key)
            analysis = stored.get("analysis") if stored and stored.get("analysis") else None
            if not analysis:
                if inline_analysis:
                    analysis = await _ensure_analysis(record)
                else:
                    # 延迟分析，先入库
                    analysis = {"analysis_provider": "pending", "needs_reanalysis": 1}
            scope = _classify_scope(record, analysis)
            if scope != "direct":
                logger.info(
                    f"[fundamental.filter] 识别为{scope}级资讯 code={code} title={record.get('title')}"
                )
            record["analysis"] = analysis
            if fundamental_storage:
                record["unique_key"] = unique_key
                existed = bool(stored)
                fundamental_storage.upsert(record)
                if existed:
                    updated_count += 1
                    if len(updated_items_log) < 3:
                        updated_items_log.append((record.get("title") or "", record.get("publish_time") or ""))
                else:
                    new_count += 1
                    if len(new_items_log) < 3:
                        new_items_log.append((record.get("title") or "", record.get("publish_time") or ""))
                if scope == "direct":
                    refreshed_direct_records.append(record)
            kept_count += 1
        logger.info(
            f"[fundamental.refresh] code={code} fetched={fetched_count} kept={kept_count} "
            f"new={new_count} updated={updated_count} "
            f"skip_no_time={skipped_no_time} skip_cutoff={skipped_cutoff} days={days}"
        )
        if new_items_log:
            logger.info("[fundamental.refresh.new_samples] %s", new_items_log)
        if updated_items_log:
            logger.info("[fundamental.refresh.updated_samples] %s", updated_items_log)
        if cutoff_items_log:
            logger.info("[fundamental.refresh.skip_cutoff_samples] %s", cutoff_items_log)
        if notime_items_log:
            logger.info("[fundamental.refresh.skip_no_time_samples] %s", notime_items_log)
    except Exception as exc:
        logger.debug(f"基本面增量搜索失败: {exc}")

    if run_remote:
        refresh_quota = max(3, min(10, max(size // 2, 1)))
        # 后台触发重算，避免阻塞刷新
        asyncio.create_task(_repair_existing_records(quota=refresh_quota))

    def _build_cached_news_signals(override_direct_records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, List[Dict[str, Any]]]:
        local_signals = {key: [] for key in signals.keys()}
        stored_records: List[Dict[str, Any]] = []
        sector_records: List[Dict[str, Any]] = []
        macro_records: List[Dict[str, Any]] = []
        preview_times: List[str] = []

        def _sort_key_by_time(rec: Dict[str, Any]):
            pt = rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen") or ""
            norm = _normalize_publish_time(pt) if pt else None
            try:
                return datetime.fromisoformat((norm or "").replace("Z", "+00:00"))
            except Exception:
                return datetime.min

        seen_keys = set()
        # 先放入本次刷新得到的direct记录
        if override_direct_records:
            for rec in override_direct_records:
                key = rec.get("unique_key")
                if not key and fundamental_storage:
                    key = fundamental_storage.make_unique_key(
                        rec.get("code", ""),
                        rec.get("title", ""),
                        rec.get("url", ""),
                        rec.get("publish_time") or rec.get("raw_publish_time"),
                    )
                    rec["unique_key"] = key
                if key and key in seen_keys:
                    continue
                if key:
                    seen_keys.add(key)
                stored_records.append(rec)

        skipped_irrelevant = 0
        def _is_relevant(rec: Dict[str, Any]) -> bool:
            # 标题/摘要包含目标关键词才认为相关
            return _has_target_token(rec)

        skipped_recs: List[Dict[str, Any]] = []
        if fundamental_storage:
            raw_records = fundamental_storage.get_recent_news(code, limit=100)
            raw_records_sorted = sorted(raw_records, key=_sort_key_by_time, reverse=True)
            recent_keep = 10  # 保底保留最新若干条，防止过度过滤
            for idx, rec in enumerate(raw_records_sorted):
                if rec.get("code") and rec.get("code") != code:
                    continue
                key = rec.get("unique_key")
                if key and key in seen_keys:
                    continue
                if not _is_relevant(rec) and idx >= recent_keep:
                    skipped_irrelevant += 1
                    skipped_recs.append(rec)
                    continue
                scope = _classify_scope(rec, rec.get("analysis"))
                if scope == "direct":
                    if key:
                        seen_keys.add(key)
                    stored_records.append(rec)
                elif scope == "sector":
                    sector_records.append(rec)
                else:
                    macro_records.append(rec)
        added_from_skipped = 0
        min_keep = 8
        if (not stored_records or len(stored_records) < min_keep) and skipped_recs:
            # 如果过滤后过少，补充被跳过的记录（按时间排序）以免列表过瘠
            logger.info(f"[fundamental.signals.cache] code={code} direct过少({len(stored_records)}), 回填被过滤的记录")
            for rec in skipped_recs:
                if len(stored_records) >= min_keep:
                    break
                key = rec.get("unique_key")
                if key and key in seen_keys:
                    continue
                scope = _classify_scope(rec, rec.get("analysis"))
                if scope != "direct":
                    continue
                if key:
                    seen_keys.add(key)
                stored_records.append(rec)
                added_from_skipped += 1

        if not stored_records and skipped_irrelevant > 0:
            logger.info(f"[fundamental.signals.cache] code={code} direct为空，放宽过滤纳入被跳过的记录")
            stored_records = []
            seen_keys = set()
            for rec in raw_records_sorted if fundamental_storage else []:
                if rec.get("code") and rec.get("code") != code:
                    continue
                key = rec.get("unique_key")
                if key and key in seen_keys:
                    continue
                scope = _classify_scope(rec, rec.get("analysis"))
                if scope == "direct":
                    if key:
                        seen_keys.add(key)
                    stored_records.append(rec)

        if not stored_records:
            logger.info(f"[fundamental.signals.cache] code={code} 本地无direct资讯，sector={len(sector_records)} macro={len(macro_records)}")
            local_signals["daily_metrics"] = []
            return local_signals
        logger.info(
            f"[fundamental.signals.cache.raw] code={code} direct={len(stored_records)} sector={len(sector_records)} macro={len(macro_records)}"
        )
        daily_buckets: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: {
                "counts": {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0},
                "weights": {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}
            }
        )
        for rec in stored_records:
            analysis = rec.get("analysis") or {}
            raw_sentiment = analysis.get("sentiment") or "neutral"
            sentiment = "neutral"
            if raw_sentiment in ("bullish", "利好", "看涨"):
                sentiment = "bullish"
            elif raw_sentiment in ("bearish", "利空", "看跌"):
                sentiment = "bearish"
            publish_time_val = rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen")
            normalized_publish_time = _normalize_publish_time(publish_time_val) if publish_time_val else None
            if normalized_publish_time and len(preview_times) < 3:
                preview_times.append(normalized_publish_time)
            entry = {
                "title": rec.get("title"),
                "snippet": rec.get("snippet"),
                "source": rec.get("source"),
                "url": rec.get("url"),
                "publish_time": normalized_publish_time or publish_time_val,
                "published_at": normalized_publish_time or publish_time_val,
                "analysis": analysis
            }
            local_signals.setdefault(sentiment, []).append(entry)
            publish_date = (normalized_publish_time or publish_time_val or "")[:10]
            if publish_date:
                bucket = daily_buckets[publish_date]
                bucket["counts"][sentiment] += 1
                impact_score = float(analysis.get("impact_score") or 50)
                novelty_score = float(analysis.get("novelty_score") or analysis.get("magnitude_score") or 50)
                weight = max(0.1, min((impact_score * 0.7 + novelty_score * 0.3) / 100, 2.0))
                if analysis.get("effectiveness") == "stale":
                    weight *= 0.3
                elif analysis.get("effectiveness") == "diminished":
                    weight *= 0.6
                bucket["weights"][sentiment] += weight
        daily_metrics = []
        for date, bucket in sorted(daily_buckets.items(), key=lambda x: x[0], reverse=True):
            counts = bucket["counts"]
            weights = bucket["weights"]
            total = counts["bullish"] + counts["bearish"] + counts["neutral"]
            total_weight = weights["bullish"] + weights["bearish"] + weights["neutral"]
            if total == 0:
                continue
            weight_score = (weights["bullish"] - weights["bearish"]) / total_weight if total_weight else 0.0
            score = (counts["bullish"] - counts["bearish"]) / total
            daily_metrics.append({
                "date": date,
                "bullish": counts["bullish"],
                "bearish": counts["bearish"],
                "neutral": counts["neutral"],
                "score": round(score, 2),
                "weighted_score": round(weight_score, 2)
            })
        local_signals["daily_metrics"] = daily_metrics
        local_signals["sector_news"] = [
            {
                "title": rec.get("title"),
                "snippet": rec.get("snippet"),
                "source": rec.get("source"),
                "url": rec.get("url"),
                "publish_time": _normalize_publish_time(rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen")) or rec.get("publish_time"),
                "analysis": rec.get("analysis"),
            }
            for rec in sector_records
        ]
        local_signals["macro_news"] = [
            {
                "title": rec.get("title"),
                "snippet": rec.get("snippet"),
                "source": rec.get("source"),
                "url": rec.get("url"),
                "publish_time": _normalize_publish_time(rec.get("publish_time") or rec.get("last_seen") or rec.get("first_seen")) or rec.get("publish_time"),
                "analysis": rec.get("analysis"),
            }
            for rec in macro_records
        ]
        local_signals["meta"] = {
            "search_query": search_query,
            "company_name": company_name,
            "skipped_irrelevant": skipped_irrelevant,
            "added_from_skipped": added_from_skipped,
            "total_direct": len(stored_records),
            "used_loose_filter": (not name_tokens) or (added_from_skipped > 0) or (not stored_records)
        }
        local_signals["summary"] = _build_fundamental_summary(local_signals)
        logger.info(
            f"[fundamental.signals.cache] code={code} bullish={len(local_signals.get('bullish', []))} "
            f"bearish={len(local_signals.get('bearish', []))} total_direct={len(stored_records)} "
            f"sector={len(sector_records)} macro={len(macro_records)} "
            f"top_publish_time={preview_times} skipped_irrelevant={skipped_irrelevant} "
            f"added_from_skipped={added_from_skipped}"
        )
        return local_signals

    return _build_cached_news_signals(
        override_direct_records=refreshed_direct_records if run_remote else None
    )


def _build_fundamental_summary(signals: Dict[str, List[Dict[str, Any]]], limit: int = 12) -> Dict[str, Any]:
    """从已分析的资讯构建一个短摘要，供多模型前置/前端展示"""
    def _parse_ts(text: Any) -> float:
        if text is None:
            return 0.0
        try:
            if isinstance(text, (int, float)):
                val = float(text)
                return val if val > 1e12 else val
            s = str(text).strip()
            if not s:
                return 0.0
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            return dt.timestamp()
        except Exception:
            return 0.0

    all_items: List[Dict[str, Any]] = []
    for key in ("bullish", "bearish", "neutral"):
        for item in signals.get(key, []):
            i = dict(item)
            i["sentiment"] = key
            all_items.append(i)
    def _ts(item: Dict[str, Any]) -> float:
        return _parse_ts(item.get("publish_time") or item.get("published_at") or item.get("last_seen"))
    sorted_items = sorted(all_items, key=_ts, reverse=True)
    top_items = sorted_items[:limit]
    counts = {
        "bullish": len(signals.get("bullish", [])),
        "bearish": len(signals.get("bearish", [])),
        "neutral": len(signals.get("neutral", [])),
    }
    latest_ts = _ts(top_items[0]) if top_items else None
    headlines = []
    for item in top_items:
        headlines.append({
            "title": item.get("title"),
            "sentiment": item.get("sentiment"),
            "publish_time": item.get("publish_time") or item.get("published_at"),
            "source": item.get("source"),
            "url": item.get("url"),
            "summary": (item.get("analysis") or {}).get("summary") or item.get("snippet")
        })
    return {
        "counts": counts,
        "latest_time": datetime.fromtimestamp(latest_ts, tz=timezone.utc).isoformat() if latest_ts else None,
        "headlines": headlines,
        "limit": limit,
    }

def _normalize_kline_cache_scope(request: HistoryKLineRequest) -> Tuple[str, str, str]:
    """生成用于缓存的K线范围标识，避免不同请求互相污染"""
    ktype_value = request.ktype.value if hasattr(request.ktype, "value") else str(request.ktype)
    autype_value = request.autype.value if hasattr(request.autype, "value") else str(request.autype)
    start_token = request.start or f"recent:{request.max_count}"
    end_token = request.end or "latest"
    return f"{ktype_value}:{autype_value}", start_token, end_token


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
def _merge_kline_records(left: Optional[List[Dict[str, Any]]], right: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not left and not right:
        return []
    if not left:
        return list(right or [])
    if not right:
        return list(left or [])
    merged: Dict[str, Dict[str, Any]] = {}
    for record in left:
        key = record.get("time_key") or record.get("time")
        if not key:
            continue
        merged[key] = dict(record)
    for record in right:
        key = record.get("time_key") or record.get("time")
        if not key:
            continue
        base = merged.get(key, {})
        base.update(record)
        merged[key] = base
    sorted_items = sorted(merged.items(), key=lambda item: item[0])
    return [item[1] for item in sorted_items]


def _build_analysis_context_text(snapshot: Dict[str, Any]) -> str:
    quote = snapshot.get("quote") or {}
    session = snapshot.get("session_window") or {}
    capital_flow = (snapshot.get("capital_flow") or {}).get("summary", {})
    capital_distribution = (snapshot.get("capital_distribution") or {}).get("summary", {})
    insights = snapshot.get("insights") or {}
    generated_at = snapshot.get("generated_at")
    missing_parts: List[str] = []
    lines = []
    if quote:
        lines.append(
            f"[行情 @ {quote.get('update_time') or generated_at}] 价格 {quote.get('price') or quote.get('cur_price')}，"
            f"涨跌幅 {quote.get('change_rate')}%，成交额 {quote.get('turnover')}，成交量 {quote.get('volume')}。"
        )
    holding = snapshot.get("holding") or {}
    if holding:
        parts = [f"{k}:{v}" for k, v in holding.items()]
        lines.append("持仓: " + " / ".join(parts))
    else:
        missing_parts.append("持仓明细")

    if session:
        break_info = ""
        if session.get("break_start") and session.get("break_end"):
            break_info = f"，午休 {session['break_start']}~{session['break_end']}"
        lines.append(
            f"交易时段: {session.get('market','未知市场')} {session.get('open_time')}~{session.get('close_time')}{break_info}"
        )
    else:
        missing_parts.append("交易时段")

    signals = snapshot.get("signals") or {}
    for sentiment in ("bullish", "bearish"):
        items = signals.get(sentiment) or []
        if items:
            highlights = "; ".join(
                f"{(item.get('title') or item.get('summary') or '').strip()} [{item.get('publish_time') or item.get('published_at')}]"
                for item in items[:3]
                if item
            )
            label = "利好" if sentiment == "bullish" else "利空"
            lines.append(f"{label}资讯: {highlights}")
    if not any(signals.get(key) for key in ("bullish", "bearish", "neutral")):
        missing_parts.append("最新资讯/新闻")

    tech_summary = insights.get("technical_summary")
    if tech_summary:
        lines.append(f"技术摘要: {tech_summary}")
    if capital_flow:
        lines.append(
            f"资金流: {capital_flow.get('overall_trend')}，主力 {capital_flow.get('main_trend')}，"
            f"最新净流入 {capital_flow.get('latest_net_inflow')}"
        )
    else:
        missing_parts.append("资金流摘要")
    if capital_distribution:
        lines.append(
            f"资金分布: 主导资金 {capital_distribution.get('dominant_fund_type')} "
            f"{capital_distribution.get('dominant_fund_amount')}，总体 {capital_distribution.get('overall_trend')}"
        )
    recommendations = snapshot.get("recommendations") or []
    if recommendations:
        latest = recommendations[0]
        lines.append(
            f"最新策略: {latest.get('action')} ({latest.get('timeframe')}) "
            f"信心 {latest.get('confidence')} 于 {latest.get('created_at')}"
        )
    quote_counts = [insights.get("signal_bullish"), insights.get("signal_bearish"), insights.get("signal_neutral")]
    if any(v is not None for v in quote_counts):
        lines.append(
            f"信号分布: 利好 {insights.get('signal_bullish', '-')}"
            f" / 利空 {insights.get('signal_bearish', '-')}"
            f" / 中性 {insights.get('signal_neutral', '-')}"
        )
    if not quote:
        missing_parts.append("实时行情")
    if missing_parts:
        lines.append("⚠️ 数据缺口: " + "、".join(missing_parts))
    return "\n".join(lines)
