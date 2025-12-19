import os
import sqlite3
import threading
import json
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta


class FundamentalNewsStorage:
    def __init__(self, db_path: str = "data/fundamental_news.db"):
        self.db_path = db_path
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fundamental_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    title TEXT,
                    url TEXT,
                    source TEXT,
                    snippet TEXT,
                    publish_time TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    unique_key TEXT UNIQUE,
                    analysis_json TEXT,
                    sentiment TEXT,
                    confidence REAL,
                    impact_horizon TEXT,
                    volatility_bias TEXT,
                    tags TEXT,
                    opportunities TEXT,
                    risks TEXT,
                    raw_payload TEXT,
                    event_type TEXT,
                    effectiveness TEXT,
                    impact_score REAL,
                    novelty_score REAL,
                    magnitude_score REAL,
                    duration_days REAL,
                    market_sensitivity TEXT,
                    historical_response TEXT,
                    trigger_conditions TEXT
                )
                """
            )
            # 兼容旧库
            columns = [row[1] for row in self._conn.execute("PRAGMA table_info(fundamental_news)").fetchall()]
            for col_sql in [
                ("event_type", "TEXT"),
                ("effectiveness", "TEXT"),
                ("impact_score", "REAL"),
                ("novelty_score", "REAL"),
                ("magnitude_score", "REAL"),
                ("duration_days", "REAL"),
                ("market_sensitivity", "TEXT"),
                ("historical_response", "TEXT"),
                ("trigger_conditions", "TEXT"),
                ("analysis_provider", "TEXT"),
                ("analysis_attempts", "INTEGER"),
                ("analysis_error", "TEXT"),
                ("needs_reanalysis", "INTEGER"),
                ("analysis_updated_at", "TEXT"),
            ]:
                if col_sql[0] not in columns:
                    self._conn.execute(f"ALTER TABLE fundamental_news ADD COLUMN {col_sql[0]} {col_sql[1]}")
            self._conn.commit()
            # 报告表
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fundamental_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    stock_name TEXT,
                    period TEXT, -- daily/weekly
                    date TEXT, -- 归属日期：日/周
                    title TEXT,
                    report TEXT,
                    items_used INTEGER,
                    days INTEGER,
                    size_limit INTEGER,
                    source TEXT,
                    meta_json TEXT,
                    created_at TEXT,
                    UNIQUE(code, period, date)
                )
                """
            )
            self._conn.commit()

    @staticmethod
    def make_unique_key(code: str, title: str, url: str, publish_time: Optional[str] = None) -> str:
        base = f"{code}|{title or ''}|{url or ''}|{publish_time or ''}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def upsert(self, record: Dict[str, Any]):
        now = datetime.utcnow().isoformat()
        rec = record.copy()
        unique_key = rec.get("unique_key") or self.make_unique_key(
            rec.get("code", ""),
            rec.get("title", ""),
            rec.get("url", ""),
            rec.get("publish_time") or rec.get("raw_publish_time")
        )
        analysis = rec.get("analysis") or {}
        tags = analysis.get("themes") or []
        opportunities = analysis.get("opportunity_factors") or []
        risks = analysis.get("risk_factors") or []
        triggers = analysis.get("trigger_conditions") or []
        historical = analysis.get("historical_response")
        provider = analysis.get("analysis_provider")
        needs_reanalysis = rec.get("needs_reanalysis")
        if needs_reanalysis is None:
            needs_reanalysis = 1 if provider == "fallback" else 0
        with self._lock, self._conn:
            cur = self._conn.execute("SELECT id FROM fundamental_news WHERE unique_key=?", (unique_key,))
            row = cur.fetchone()
            if row:
                self._conn.execute(
                    """
                    UPDATE fundamental_news
                    SET last_seen=?, analysis_json=?, sentiment=?, confidence=?, impact_horizon=?, volatility_bias=?,
                        tags=?, opportunities=?, risks=?, raw_payload=?, event_type=?, effectiveness=?, impact_score=?,
                        novelty_score=?, magnitude_score=?, duration_days=?, market_sensitivity=?, historical_response=?, trigger_conditions=?,
                        analysis_provider=?, analysis_attempts=COALESCE(analysis_attempts, 0)+1, analysis_error=NULL,
                        needs_reanalysis=?, analysis_updated_at=?
                    WHERE unique_key=?
                    """,
                    (
                        now,
                        json.dumps(analysis, ensure_ascii=False),
                        analysis.get("sentiment"),
                        analysis.get("confidence"),
                        analysis.get("impact_horizon"),
                        analysis.get("volatility_bias"),
                        json.dumps(tags, ensure_ascii=False),
                        json.dumps(opportunities, ensure_ascii=False),
                        json.dumps(risks, ensure_ascii=False),
                        json.dumps(rec, ensure_ascii=False),
                        analysis.get("event_type"),
                        analysis.get("effectiveness"),
                        analysis.get("impact_score"),
                        analysis.get("novelty_score"),
                        analysis.get("magnitude_score"),
                        analysis.get("duration_days"),
                        analysis.get("market_sensitivity"),
                        json.dumps(historical, ensure_ascii=False) if historical is not None else None,
                        json.dumps(triggers, ensure_ascii=False),
                        provider,
                        needs_reanalysis,
                        now,
                        unique_key
                    )
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO fundamental_news (
                        code,title,url,source,snippet,publish_time,first_seen,last_seen,unique_key,
                        analysis_json,sentiment,confidence,impact_horizon,volatility_bias,tags,opportunities,risks,raw_payload,
                        event_type,effectiveness,impact_score,novelty_score,magnitude_score,duration_days,market_sensitivity,historical_response,trigger_conditions,
                        analysis_provider,analysis_attempts,analysis_error,needs_reanalysis,analysis_updated_at
                    ) VALUES (:code,:title,:url,:source,:snippet,:publish_time,:first_seen,:last_seen,:unique_key,
                        :analysis_json,:sentiment,:confidence,:impact_horizon,:volatility_bias,:tags,:opportunities,:risks,:raw_payload,
                        :event_type,:effectiveness,:impact_score,:novelty_score,:magnitude_score,:duration_days,:market_sensitivity,:historical_response,:trigger_conditions,
                        :analysis_provider,:analysis_attempts,:analysis_error,:needs_reanalysis,:analysis_updated_at)
                    """,
                    {
                        "code": rec.get("code"),
                        "title": rec.get("title"),
                        "url": rec.get("url"),
                        "source": rec.get("source"),
                        "snippet": rec.get("snippet"),
                        "publish_time": rec.get("publish_time"),
                        "first_seen": now,
                        "last_seen": now,
                        "unique_key": unique_key,
                        "analysis_json": json.dumps(analysis, ensure_ascii=False),
                        "sentiment": analysis.get("sentiment"),
                        "confidence": analysis.get("confidence"),
                        "impact_horizon": analysis.get("impact_horizon"),
                        "volatility_bias": analysis.get("volatility_bias"),
                        "tags": json.dumps(tags, ensure_ascii=False),
                        "opportunities": json.dumps(opportunities, ensure_ascii=False),
                        "risks": json.dumps(risks, ensure_ascii=False),
                        "raw_payload": json.dumps(rec, ensure_ascii=False),
                        "event_type": analysis.get("event_type"),
                        "effectiveness": analysis.get("effectiveness"),
                        "impact_score": analysis.get("impact_score"),
                        "novelty_score": analysis.get("novelty_score"),
                        "magnitude_score": analysis.get("magnitude_score"),
                        "duration_days": analysis.get("duration_days"),
                        "market_sensitivity": analysis.get("market_sensitivity"),
                        "historical_response": json.dumps(historical, ensure_ascii=False) if historical is not None else None,
                        "trigger_conditions": json.dumps(triggers, ensure_ascii=False),
                        "analysis_provider": provider,
                        "analysis_attempts": 1,
                        "analysis_error": None,
                        "needs_reanalysis": needs_reanalysis,
                        "analysis_updated_at": now
                    }
                )
            self._conn.commit()

    def get_recent_news(self, code: str, limit: int = 30) -> List[Dict[str, Any]]:
        with self._lock, self._conn:
            rows = self._conn.execute(
                """
                SELECT * FROM fundamental_news
                WHERE code=?
                ORDER BY COALESCE(last_seen, publish_time, first_seen) DESC,
                         COALESCE(publish_time, last_seen) DESC
                LIMIT ?
                """,
                (code, limit)
            ).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for field in ("analysis_json", "tags", "opportunities", "risks", "raw_payload", "historical_response", "trigger_conditions"):
                if field in item and item[field] is not None:
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            if item.get("analysis_json") and isinstance(item["analysis_json"], dict):
                item["analysis"] = item["analysis_json"]
            else:
                item["analysis"] = {}
            results.append(item)
        return results

    def get_news_since(self, code: str, days: int = 3, limit: int = 100) -> List[Dict[str, Any]]:
        """获取近 days 天的资讯（按 publish_time/last_seen 排序），用于汇总分析"""
        try:
            cutoff_dt = datetime.utcnow() - timedelta(days=max(1, days))
        except Exception:
            cutoff_dt = datetime.utcnow()

        def _parse_ts(text: Any) -> float:
            if text is None:
                return 0.0
            try:
                if isinstance(text, (int, float)):
                    return float(text)
                s = str(text).strip()
                if not s:
                    return 0.0
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                dt = datetime.fromisoformat(s)
                return dt.timestamp()
            except Exception:
                return 0.0

        all_rows = self.get_recent_news(code, limit=limit * 2)
        filtered = []
        cutoff_ts = cutoff_dt.timestamp()
        for row in all_rows:
            ts = _parse_ts(row.get("publish_time") or row.get("last_seen") or row.get("first_seen"))
            if ts >= cutoff_ts:
                filtered.append(row)
        filtered_sorted = sorted(
            filtered,
            key=lambda x: _parse_ts(x.get("publish_time") or x.get("last_seen") or x.get("first_seen")),
            reverse=True
        )
        return filtered_sorted[:limit]

    def upsert_report(self, report: Dict[str, Any]):
        now = datetime.utcnow().isoformat()
        rec = report.copy()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO fundamental_reports (code, stock_name, period, date, title, report, items_used, days, size_limit, source, meta_json, created_at)
                VALUES (:code, :stock_name, :period, :date, :title, :report, :items_used, :days, :size_limit, :source, :meta_json, :created_at)
                ON CONFLICT(code, period, date) DO UPDATE SET
                    stock_name=excluded.stock_name,
                    title=excluded.title,
                    report=excluded.report,
                    items_used=excluded.items_used,
                    days=excluded.days,
                    size_limit=excluded.size_limit,
                    source=excluded.source,
                    meta_json=excluded.meta_json,
                    created_at=excluded.created_at
                """,
                {
                    "code": rec.get("code"),
                    "stock_name": rec.get("stock_name"),
                    "period": rec.get("period"),
                    "date": rec.get("date"),
                    "title": rec.get("title"),
                    "report": rec.get("report"),
                    "items_used": rec.get("items_used"),
                    "days": rec.get("days"),
                    "size_limit": rec.get("size_limit"),
                    "source": rec.get("source"),
                    "meta_json": json.dumps(rec.get("meta") or {}, ensure_ascii=False),
                    "created_at": now,
                },
            )
            self._conn.commit()

    def list_reports(self, code: str, period: Optional[str] = None, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM fundamental_reports WHERE code=?"
        params: List[Any] = [code]
        if period:
            sql += " AND period=?"
            params.append(period)
        sql += " ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._lock, self._conn:
            rows = self._conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            rec = dict(row)
            if rec.get("meta_json"):
                try:
                    rec["meta"] = json.loads(rec["meta_json"])
                except Exception:
                    rec["meta"] = {}
            results.append(rec)
        return results

    def get_report(self, code: str, period: str, date: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT * FROM fundamental_reports WHERE code=? AND period=? AND date=?",
                (code, period, date),
            ).fetchone()
        if not row:
            return None
        rec = dict(row)
        if rec.get("meta_json"):
            try:
                rec["meta"] = json.loads(rec["meta_json"])
            except Exception:
                rec["meta"] = {}
        return rec

    def get_report_by_id(self, report_id: int) -> Optional[Dict[str, Any]]:
        with self._lock, self._conn:
            row = self._conn.execute("SELECT * FROM fundamental_reports WHERE id=?", (report_id,)).fetchone()
        if not row:
            return None
        rec = dict(row)
        if rec.get("meta_json"):
            try:
                rec["meta"] = json.loads(rec["meta_json"])
            except Exception:
                rec["meta"] = {}
        return rec

    def get_by_unique_key(self, unique_key: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT * FROM fundamental_news WHERE unique_key=?",
                (unique_key,)
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        if item.get("analysis_json"):
            try:
                item["analysis"] = json.loads(item["analysis_json"])
            except Exception:
                item["analysis"] = None
        return item

    def get_reanalysis_queue(self, code: str, limit: int = 5) -> List[Dict[str, Any]]:
        with self._lock, self._conn:
            rows = self._conn.execute(
                """
                SELECT * FROM fundamental_news
                WHERE code=? AND (needs_reanalysis=1 OR sentiment IS NULL OR sentiment='')
                ORDER BY COALESCE(last_seen, first_seen) DESC
                LIMIT ?
                """,
                (code, limit)
            ).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for field in ("analysis_json", "tags", "opportunities", "risks", "raw_payload", "historical_response", "trigger_conditions"):
                if field in item and item[field] is not None:
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            if item.get("analysis_json") and isinstance(item["analysis_json"], dict):
                item["analysis"] = item["analysis_json"]
            else:
                item["analysis"] = {}
            results.append(item)
        return results

    def list_news(
        self,
        code: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []
        if code:
            conditions.append("code=?")
            params.append(code)
        if start_date:
            conditions.append("COALESCE(publish_time, last_seen) >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("COALESCE(publish_time, last_seen) <= ?")
            params.append(end_date)
        if status:
            status_lower = status.lower()
            if status_lower == "pending":
                conditions.append(
                    "(needs_reanalysis=1 OR analysis_provider IS NULL OR analysis_provider='' OR analysis_provider='pending')"
                )
            elif status_lower == "fail":
                conditions.append("analysis_provider='fail'")
            elif status_lower == "done":
                conditions.append(
                    "(analysis_provider IS NOT NULL AND analysis_provider NOT IN ('pending','fail') AND COALESCE(needs_reanalysis,0)=0)"
                )
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM fundamental_news
            WHERE {where_clause}
            ORDER BY COALESCE(publish_time, last_seen) DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        with self._lock, self._conn:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for field in ("analysis_json", "tags", "opportunities", "risks", "raw_payload", "historical_response", "trigger_conditions"):
                if field in item and item[field] is not None:
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            if item.get("analysis_json") and isinstance(item["analysis_json"], dict):
                item["analysis"] = item["analysis_json"]
            else:
                item["analysis"] = {}
            results.append(item)
        return results
