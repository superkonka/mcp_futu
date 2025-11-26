import json
import os
import threading
from typing import Dict, Any


class DashboardSessionStore:
    """简单的会话持久化，防止服务重启后 session 丢失"""

    def __init__(self, path: str = "data/dashboard_sessions.json"):
        self.path = path
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()

    def load(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(self.path):
            return {}
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    def save(self, sessions: Dict[str, Dict[str, Any]]):
        with self._lock:
            payload = {}
            for session_id, info in sessions.items():
                payload[session_id] = {
                    "code": info.get("code"),
                    "nickname": info.get("nickname"),
                    "created_at": info.get("created_at")
                }
            tmp_path = f"{self.path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
