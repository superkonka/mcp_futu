import sqlite3
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class MinuteKlineStorage:
    """轻量级SQLite存储，用于缓存已订阅股票的1分钟K线数据"""

    def __init__(self, db_path: str = "data/minute_kline.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS minute_kline (
                    code TEXT NOT NULL,
                    time_key TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    turnover REAL,
                    extra TEXT,
                    PRIMARY KEY (code, time_key)
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_minute_kline_code_time ON minute_kline(code, time_key)"
            )
            self._conn.commit()

    def save_batch(self, code: str, records: Iterable[Dict[str, object]]) -> None:
        rows: List[tuple] = []
        for record in records:
            time_key = record.get("time_key") or record.get("time")
            if not time_key:
                continue
            rows.append(
                (
                    code,
                    str(time_key),
                    self._to_float(record.get("open")),
                    self._to_float(record.get("high")),
                    self._to_float(record.get("low")),
                    self._to_float(record.get("close")),
                    self._to_float(record.get("volume")),
                    self._to_float(record.get("turnover")),
                    None,
                )
            )
        if not rows:
            return
        with self._lock, self._conn:
            self._conn.executemany(
                """
                INSERT INTO minute_kline (code, time_key, open, high, low, close, volume, turnover, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, time_key) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    turnover=excluded.turnover
                """,
                rows,
            )
            self._conn.commit()

    def fetch_recent(self, code: str, limit: int = 720) -> List[Dict[str, object]]:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "SELECT code, time_key, open, high, low, close, volume, turnover FROM minute_kline"
                " WHERE code=? ORDER BY time_key DESC LIMIT ?",
                (code, limit),
            )
            rows = cursor.fetchall()
        result = []
        for row in reversed(rows):
            result.append(
                {
                    "code": row[0],
                    "time_key": row[1],
                    "open": row[2],
                    "high": row[3],
                    "low": row[4],
                    "close": row[5],
                    "volume": row[6],
                    "turnover": row[7],
                }
            )
        return result

    def delete_older_than(self, code: str, keep_limit: int = 1440) -> None:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "SELECT time_key FROM minute_kline WHERE code=? ORDER BY time_key DESC LIMIT 1 OFFSET ?",
                (code, keep_limit),
            )
            row = cursor.fetchone()
            if not row:
                return
            threshold = row[0]
            self._conn.execute(
                "DELETE FROM minute_kline WHERE code=? AND time_key < ?",
                (code, threshold),
            )
            self._conn.commit()

    @staticmethod
    def _to_float(value: Optional[object]) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except Exception:
            return None
