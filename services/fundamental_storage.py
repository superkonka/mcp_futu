import os
import sqlite3
import threading
import json
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime


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

    @staticmethod
    def make_unique_key(code: str, title: str, url: str) -> str:
        base = f"{code}|{title or ''}|{url or ''}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def upsert(self, record: Dict[str, Any]):
        now = datetime.utcnow().isoformat()
        rec = record.copy()
        unique_key = rec.get("unique_key") or self.make_unique_key(rec.get("code", ""), rec.get("title", ""), rec.get("url", ""))
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
                ORDER BY COALESCE(publish_time, last_seen) DESC
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
