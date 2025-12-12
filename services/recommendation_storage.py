import sqlite3
import json
import threading
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone


class RecommendationStorageService:
    def __init__(self, db_path: str = "recommendations.db"):
        self.db_path = db_path
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        self._init_eval_history()

    def _init_db(self):
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    action TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    confidence REAL,
                    timeframe TEXT,
                    status TEXT DEFAULT 'draft',
                    tags TEXT,
                    source TEXT,
                    evidence TEXT,
                    created_at TEXT NOT NULL,
                    adopted INTEGER DEFAULT 0,
                    adopted_at TEXT,
                    outcome TEXT,
                    entry_price REAL,
                    target_price REAL,
                    stop_loss REAL,
                    valid_until TEXT,
                    eval_status TEXT,
                    eval_pnl REAL,
                    eval_summary TEXT,
                    eval_generated_at TEXT,
                    monitor_config TEXT,
                    analysis_context TEXT,
                    model_results TEXT,
                    judge_result TEXT
                )
                """
            )
            # 兼容旧版本数据库
            self._ensure_column("status", "TEXT")
            self._conn.execute("UPDATE recommendations SET status = 'draft' WHERE status IS NULL")
            self._ensure_column("entry_price", "REAL")
            self._ensure_column("target_price", "REAL")
            self._ensure_column("stop_loss", "REAL")
            self._ensure_column("valid_until", "TEXT")
            self._ensure_column("eval_status", "TEXT")
            self._ensure_column("eval_pnl", "REAL")
            self._ensure_column("eval_summary", "TEXT")
            self._ensure_column("eval_generated_at", "TEXT")
            self._ensure_column("eval_detail", "TEXT")
            self._ensure_column("monitor_config", "TEXT")
            self._ensure_column("analysis_context", "TEXT")
            self._ensure_column("model_results", "TEXT")
            self._ensure_column("judge_result", "TEXT")
            self._conn.commit()

    def _init_eval_history(self):
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendation_eval_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recommendation_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    summary TEXT,
                    pnl REAL,
                    detail TEXT,
                    models TEXT,
                    judge_model TEXT,
                    FOREIGN KEY(recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recommendation_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    level TEXT,
                    message TEXT,
                    payload TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.commit()

    def _ensure_column(self, column: str, col_type: str):
        cursor = self._conn.execute(
            "SELECT name FROM pragma_table_info('recommendations') WHERE name=?",
            (column,)
        )
        if cursor.fetchone():
            return
        self._conn.execute(f"ALTER TABLE recommendations ADD COLUMN {column} {col_type}")

    def save_recommendation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        tags = data.get("tags", [])
        evidence = data.get("evidence", [])
        payload = {
            "code": data["code"],
            "action": data["action"],
            "rationale": data["rationale"],
            "confidence": data.get("confidence"),
            "timeframe": data.get("timeframe"),
            "status": data.get("status", "draft"),
            "adopted": 1 if data.get("adopted", False) else 0,
            "tags": json.dumps(tags, ensure_ascii=False),
            "source": data.get("source"),
            "evidence": json.dumps(evidence, ensure_ascii=False),
            "created_at": now,
            "adopted_at": data.get("adopted_at"),
            "outcome": json.dumps(data.get("outcome")) if data.get("outcome") is not None else None,
            "entry_price": data.get("entry_price"),
            "target_price": data.get("target_price"),
            "stop_loss": data.get("stop_loss"),
            "valid_until": data.get("valid_until"),
            "eval_status": data.get("eval_status"),
            "eval_pnl": data.get("eval_pnl_pct"),
            "eval_summary": data.get("eval_summary"),
            "eval_generated_at": data.get("eval_generated_at"),
            "monitor_config": json.dumps(data.get("monitor_config"), ensure_ascii=False) if data.get("monitor_config") else None,
            "eval_detail": data.get("eval_detail"),
            "analysis_context": json.dumps(data.get("analysis_context"), ensure_ascii=False) if data.get("analysis_context") else None,
            "model_results": json.dumps(data.get("model_results"), ensure_ascii=False) if data.get("model_results") else None,
            "judge_result": json.dumps(data.get("judge_result"), ensure_ascii=False) if data.get("judge_result") else None,
        }
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO recommendations
                (code, action, rationale, confidence, timeframe, status, tags, source, evidence, created_at, adopted, adopted_at, outcome,
                 entry_price, target_price, stop_loss, valid_until, eval_status, eval_pnl, eval_summary, eval_generated_at, monitor_config, eval_detail,
                 analysis_context, model_results, judge_result)
                VALUES (:code, :action, :rationale, :confidence, :timeframe, :status, :tags, :source, :evidence, :created_at, :adopted, :adopted_at, :outcome,
                 :entry_price, :target_price, :stop_loss, :valid_until, :eval_status, :eval_pnl, :eval_summary, :eval_generated_at, :monitor_config, :eval_detail,
                 :analysis_context, :model_results, :judge_result)
                """,
                payload,
            )
            self._conn.commit()
            rec_id = cur.lastrowid

        return {"id": rec_id, "created_at": now}

    def get_recommendations(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM recommendations WHERE 1=1"
        params: Dict[str, Any] = {}

        def add_clause(cond: str, key: str, transform=lambda x: x):
            nonlocal sql
            val = query.get(key)
            if val is not None and val != "":
                sql += " " + cond
                params[key] = transform(val)

        add_clause("AND code = :code", "code")
        add_clause("AND action = :action", "action")

        if "adopted" in query and query["adopted"] is not None:
            sql += " AND adopted = :adopted"
            params["adopted"] = 1 if query["adopted"] else 0

        add_clause("AND created_at >= :start", "start")
        add_clause("AND created_at <= :end", "end")
        add_clause("AND source = :source", "source")

        tag = query.get("tag")
        if tag:
            sql += " AND tags LIKE :tag_like"
            params["tag_like"] = f'%"{tag}"%'

        limit = int(query.get("limit", 50))
        offset = int(query.get("offset", 0))
        sql += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        with self._lock, self._conn:
            rows = self._conn.execute(sql, params).fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            for k in ("tags", "evidence", "outcome"):
                if item.get(k):
                    try:
                        item[k] = json.loads(item[k])
                    except Exception:
                        pass
            item["adopted"] = bool(item.get("adopted", 0))
            if item.get("monitor_config"):
                try:
                    item["monitor_config"] = json.loads(item["monitor_config"])
                except Exception:
                    pass
            for field in ("analysis_context", "model_results", "judge_result"):
                if item.get(field):
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            if item.get("eval_detail"):
                try:
                    item["eval_detail"] = json.loads(item["eval_detail"])
                except Exception:
                    pass
            if "eval_pnl" in item:
                item["eval_pnl_pct"] = item.pop("eval_pnl")
            results.append(item)
        return results

    def get_recommendation(self, rec_id: int) -> Optional[Dict[str, Any]]:
        with self._conn:
            row = self._conn.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        for k in ("tags", "evidence", "outcome", "analysis_context", "model_results", "judge_result"):
            if item.get(k):
                try:
                    item[k] = json.loads(item[k])
                except Exception:
                    pass
        if item.get("eval_detail"):
            try:
                item["eval_detail"] = json.loads(item["eval_detail"])
            except Exception:
                pass
        if item.get("monitor_config"):
            try:
                item["monitor_config"] = json.loads(item["monitor_config"])
            except Exception:
                pass
        item["adopted"] = bool(item.get("adopted", 0))
        if "eval_pnl" in item:
            item["eval_pnl_pct"] = item.pop("eval_pnl")
        return item

    def update_recommendation(self, rec_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fields = []
        params: Dict[str, Any] = {"id": rec_id}
        if "adopted" in payload and payload["adopted"] is not None:
            fields.append("adopted = :adopted")
            params["adopted"] = 1 if payload["adopted"] else 0
            if payload.get("adopted"):
                params["adopted_at"] = payload.get("adopted_at") or datetime.now(timezone.utc).isoformat()
                fields.append("adopted_at = :adopted_at")
            else:
                fields.append("adopted_at = NULL")
        for key in ("eval_status", "eval_summary", "eval_generated_at"):
            if payload.get(key) is not None:
                fields.append(f"{key} = :{key}")
                params[key] = payload[key]
        if "eval_pnl_pct" in payload and payload["eval_pnl_pct"] is not None:
            fields.append("eval_pnl = :eval_pnl")
            params["eval_pnl"] = payload["eval_pnl_pct"]
        if "eval_detail" in payload and payload["eval_detail"] is not None:
            fields.append("eval_detail = :eval_detail")
            detail_value = payload["eval_detail"]
            if isinstance(detail_value, (dict, list)):
                detail_value = json.dumps(detail_value, ensure_ascii=False)
            params["eval_detail"] = detail_value
        if payload.get("monitor_config") is not None:
            fields.append("monitor_config = :monitor_config")
            monitor_value = payload["monitor_config"]
            if isinstance(monitor_value, (dict, list)):
                monitor_value = json.dumps(monitor_value, ensure_ascii=False)
            params["monitor_config"] = monitor_value
        if payload.get("status"):
            fields.append("status = :status")
            params["status"] = payload["status"]
        if not fields:
            return self.get_recommendation(rec_id)
        sql = f"UPDATE recommendations SET {', '.join(fields)} WHERE id = :id"
        with self._lock, self._conn:
            cur = self._conn.execute(sql, params)
            if cur.rowcount == 0:
                return None
            self._conn.commit()
        return self.get_recommendation(rec_id)

    def has_running_strategy(self, code: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT id FROM recommendations WHERE code = ? AND status = 'running'"
        params: List[Any] = [code]
        if exclude_id is not None:
            sql += " AND id != ?"
            params.append(exclude_id)
        with self._conn:
            row = self._conn.execute(sql, params).fetchone()
        return row is not None

    def list_running_strategies(self) -> List[Dict[str, Any]]:
        with self._conn:
            rows = self._conn.execute("SELECT * FROM recommendations WHERE status = 'running'").fetchall()
        results = []
        for row in rows:
            item = dict(row)
            for key in ("tags", "evidence", "analysis_context", "model_results", "judge_result", "monitor_config"):
                if item.get(key):
                    try:
                        item[key] = json.loads(item[key])
                    except Exception:
                        pass
            results.append(item)
        return results

    def add_evaluation_record(
        self,
        rec_id: int,
        *,
        summary: Optional[str],
        pnl: Optional[float],
        detail: Optional[Dict[str, Any]],
        models: Optional[List[str]],
        judge_model: Optional[str],
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        record_time = created_at or datetime.now(timezone.utc).isoformat()
        payload = {
            "recommendation_id": rec_id,
            "created_at": record_time,
            "summary": summary,
            "pnl": pnl,
            "detail": json.dumps(detail, ensure_ascii=False) if detail is not None else None,
            "models": json.dumps(models, ensure_ascii=False) if models is not None else None,
            "judge_model": judge_model,
        }
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO recommendation_eval_history
                (recommendation_id, created_at, summary, pnl, detail, models, judge_model)
                VALUES (:recommendation_id, :created_at, :summary, :pnl, :detail, :models, :judge_model)
                """,
                payload,
            )
            self._conn.commit()
            rec_id_new = cur.lastrowid
        return {
            "id": rec_id_new,
            "created_at": record_time,
            "summary": summary,
            "pnl": pnl,
            "detail": detail,
            "models": models,
            "judge_model": judge_model,
        }

    def get_evaluations(self, rec_id: int) -> List[Dict[str, Any]]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT * FROM recommendation_eval_history WHERE recommendation_id = ? ORDER BY created_at DESC",
                (rec_id,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            if item.get("detail"):
                try:
                    item["detail"] = json.loads(item["detail"])
                except Exception:
                    pass
            if item.get("models"):
                try:
                    item["models"] = json.loads(item["models"])
                except Exception:
                    pass
            results.append(item)
        return results

    def add_alert(
        self,
        rec_id: int,
        code: str,
        alert_type: str,
        message: str,
        level: str = "info",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO strategy_alerts (recommendation_id, code, alert_type, level, message, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    code,
                    alert_type,
                    level,
                    message,
                    json.dumps(payload, ensure_ascii=False) if payload else None,
                    created_at,
                ),
            )
            self._conn.commit()
            alert_id = cur.lastrowid
        return {
            "id": alert_id,
            "recommendation_id": rec_id,
            "code": code,
            "alert_type": alert_type,
            "level": level,
            "message": message,
            "payload": payload,
            "created_at": created_at,
        }

    def get_alerts(self, rec_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT * FROM strategy_alerts WHERE recommendation_id = ? ORDER BY created_at DESC LIMIT ?",
                (rec_id, limit),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            if item.get("payload"):
                try:
                    item["payload"] = json.loads(item["payload"])
                except Exception:
                    pass
            results.append(item)
        return results
