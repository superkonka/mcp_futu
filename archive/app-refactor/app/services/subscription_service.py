import asyncio
import time
from typing import Dict, List, Set, Any, DefaultDict
from loguru import logger

class SubscriptionManager:
    """订阅管理器：管理客户端订阅与消息分发（单播）"""

    def __init__(self):
        # 客户端消息队列：client_id -> asyncio.Queue
        self.client_queues: Dict[str, asyncio.Queue] = {}
        # 客户端订阅标的：client_id -> Set[symbol]
        self.client_symbols: DefaultDict[str, Set[str]] = DefaultDict(set)
        # 反向索引：symbol -> Set[client_id]
        self.symbol_clients: DefaultDict[str, Set[str]] = DefaultDict(set)
        # 最近心跳时间：client_id -> timestamp
        self.client_heartbeat: Dict[str, float] = {}
        # 客户端元数据：client_id -> dict
        self.client_metadata: Dict[str, Dict[str, Any]] = {}
        # 读写锁
        self._lock = asyncio.Lock()

    async def register(self, client_id: str, metadata: Dict[str, Any] = None) -> asyncio.Queue:
        """注册客户端，返回其消息队列"""
        async with self._lock:
            if client_id not in self.client_queues:
                self.client_queues[client_id] = asyncio.Queue(maxsize=1000)
                if metadata:
                    self.client_metadata[client_id] = metadata
                    self.client_metadata[client_id]['created_at'] = time.time()
            self.client_heartbeat[client_id] = time.time()
            return self.client_queues[client_id]

    async def subscribe(self, client_id: str, symbols: List[str]):
        """为客户端添加订阅标的"""
        async with self._lock:
            if client_id not in self.client_queues:
                self.client_queues[client_id] = asyncio.Queue(maxsize=1000)
            for sym in symbols:
                self.client_symbols[client_id].add(sym)
                self.symbol_clients[sym].add(client_id)
            self.client_heartbeat[client_id] = time.time()

    async def unsubscribe_all(self, client_id: str):
        """取消客户端的所有订阅"""
        async with self._lock:
            for sym in list(self.client_symbols.get(client_id, set())):
                self.symbol_clients[sym].discard(client_id)
            self.client_symbols.pop(client_id, None)

    async def unregister(self, client_id: str):
        """注销客户端"""
        async with self._lock:
            await self.unsubscribe_all(client_id)
            self.client_heartbeat.pop(client_id, None)
            self.client_metadata.pop(client_id, None)
            q = self.client_queues.pop(client_id, None)
            if q:
                try:
                    q.put_nowait({"type": "close"})
                except Exception:
                    pass

    async def broadcast_quotes(self, quotes: List[Dict[str, Any]]):
        """按订阅关系将报价单播到对应客户端队列"""
        if not quotes:
            return
        
        code_to_quote = {}
        for q in quotes:
            code = q.get("code") or q.get("security") or q.get("symbol")
            if code:
                code_to_quote[code] = q

        async with self._lock:
            for code, quote in code_to_quote.items():
                clients = self.symbol_clients.get(code, set())
                if not clients:
                    continue
                payload = {
                    "type": "quote",
                    "code": code,
                    "quote": quote,
                    "timestamp": time.time()
                }
                for cid in list(clients):
                    q = self.client_queues.get(cid)
                    if q:
                        if q.full():
                            try:
                                q.get_nowait()
                            except Exception:
                                pass
                        await q.put(payload)

    async def heartbeat(self, client_id: str):
        """更新心跳"""
        async with self._lock:
            self.client_heartbeat[client_id] = time.time()

    async def cleanup_stale_clients(self, stale_after_sec: int = 60):
        """清理过期客户端"""
        while True:
            await asyncio.sleep(30)
            now = time.time()
            async with self._lock:
                stale_ids = [cid for cid, ts in self.client_heartbeat.items() if now - ts > stale_after_sec]
                for cid in stale_ids:
                    logger.info(f"Cleaning up stale client: {cid}")
                    await self.unregister(cid)

    async def get_all_sessions(self) -> List[Dict[str, Any]]:
        """获取所有会话信息"""
        async with self._lock:
            sessions = []
            for cid, meta in self.client_metadata.items():
                session_info = {
                    "session_id": cid,
                    **meta
                }
                sessions.append(session_info)
            return sessions

subscription_manager = SubscriptionManager()
