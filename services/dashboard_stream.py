import asyncio
import json
import contextlib
from collections import defaultdict
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
import time
import os

import futu as ft
import pandas as pd
from loguru import logger

if TYPE_CHECKING:  # pragma: no cover
    from services.minute_kline_storage import MinuteKlineStorage


def _df_to_records(df: Optional[pd.DataFrame], limit: Optional[int] = None):
    if df is None:
        return []
    if limit:
        df = df.head(limit)
    try:
        return json.loads(df.to_json(orient="records"))
    except Exception:
        return []


def _normalize_levels(items, top: int = 10):
    levels = []
    if not isinstance(items, list):
        return levels
    for level in items[:top]:
        price = None
        volume = None
        if isinstance(level, (list, tuple)) and len(level) >= 2:
            price, volume = level[0], level[1]
        elif isinstance(level, dict):
            price = level.get("price") or level.get("Price")
            volume = level.get("volume") or level.get("Volume") or level.get("qty") or level.get("Qty")
        if price is None:
            continue
        try:
            price = float(price)
        except Exception:
            continue
        try:
            volume = float(volume) if volume is not None else None
        except Exception:
            volume = None
        levels.append({"price": price, "volume": volume})
    return levels


class DashboardStreamManager:
    """管理Futu订阅并向Web看板推送实时数据"""

    def __init__(self, futu_service, loop: asyncio.AbstractEventLoop, kline_storage: Optional["MinuteKlineStorage"] = None):
        self.futu_service = futu_service
        self.debug_stream = os.getenv("DASHBOARD_STREAM_DEBUG", "false").lower() == "true"
        self.loop = loop
        self.quote_ctx = getattr(futu_service, "quote_ctx", None)
        self.subtypes = [
            ft.SubType.QUOTE,
            ft.SubType.ORDER_BOOK,
            ft.SubType.TICKER,
            ft.SubType.BROKER,
            ft.SubType.RT_DATA,
            ft.SubType.K_1M,
        ]
        self.session_queues: Dict[str, asyncio.Queue] = {}
        self.session_codes: Dict[str, str] = {}
        self.code_sessions = defaultdict(set)
        self.subscribed_codes = set()
        self.code_state: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._guard_task: Optional[asyncio.Task] = None
        self.guard_interval = 60
        self.kline_tasks: Dict[str, asyncio.Task] = {}
        self.kline_poll_interval = 30
        self.kline_latest_ts: Dict[str, str] = {}
        self.kline_storage: Optional["MinuteKlineStorage"] = kline_storage
        self.kline_tasks: Dict[str, asyncio.Task] = {}
        self.kline_poll_interval = 30
        self.kline_latest_ts: Dict[str, str] = {}
        self._quote_ctx_started = False
        self.heartbeat_interval = 5
        self._heartbeat_task: Optional[asyncio.Task] = None
        if self.quote_ctx:
            self._register_handlers()
            self._ensure_quote_ctx_started()
        self._quote_log_ts: Dict[str, float] = defaultdict(float)
        self._broadcast_log_ts: Dict[str, float] = defaultdict(float)
        self._start_heartbeat()

    def _register_handlers(self):
        self.quote_ctx.set_handler(self.StockQuoteHandler(self))
        self.quote_ctx.set_handler(self.OrderBookHandler(self))
        self.quote_ctx.set_handler(self.TickerHandler(self))
        self.quote_ctx.set_handler(self.BrokerHandler(self))
        self.quote_ctx.set_handler(self.RTDataHandler(self))
        self.quote_ctx.set_handler(self.KLineHandler(self))
        logger.info("✅ DashboardStreamManager 已注册Futu推送回调")

    def register_session(self, session_id: str, code: str):
        self.session_codes[session_id] = code
        self.code_sessions[code].add(session_id)

    async def unregister_session(self, session_id: str):
        code = self.session_codes.pop(session_id, None)
        if code:
            sessions = self.code_sessions.get(code)
            if sessions:
                sessions.discard(session_id)
                if not sessions:
                    self.code_sessions.pop(code, None)
                    await self._maybe_unsubscribe(code)

    async def attach_session(self, session_id: str, code: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.session_queues[session_id] = queue
        if session_id not in self.session_codes:
            self.register_session(session_id, code)
        await self._ensure_subscription(code)
        snapshot = self._compose_snapshot(code)
        if snapshot:
            await queue.put(snapshot)
        logger.info(
            "[dashboard.stream.session.attach] session={} code={} snapshot_keys={}",
            session_id,
            code,
            list(snapshot.keys()) if snapshot else [],
        )
        return queue

    async def release_stream(self, session_id: str):
        queue = self.session_queues.pop(session_id, None)
        if queue:
            while not queue.empty():
                queue.get_nowait()
        logger.info("[dashboard.stream.session.release] session={}", session_id)
        # 保留session映射，避免取消订阅

    async def detach_session(self, session_id: str):
        await self.release_stream(session_id)
        code = self.session_codes.pop(session_id, None)
        if code:
            sessions = self.code_sessions.get(code)
            if sessions:
                sessions.discard(session_id)
                if not sessions:
                    await self._maybe_unsubscribe(code)
        await self._maybe_stop_guard()

    async def force_detach_session(self, session_id: str):
        await self.detach_session(session_id)

    async def _ensure_subscription(self, code: str):
        if not self.quote_ctx:
            return
        if code in self.subscribed_codes:
            self._ensure_kline_poll(code)
            return
        try:
            ret, msg = await asyncio.to_thread(self.quote_ctx.subscribe, code, self.subtypes)
            if ret == ft.RET_OK:
                self.subscribed_codes.add(code)
                logger.info(f"📡 Dashboard订阅 {code} 成功")
                self._ensure_kline_poll(code)
            else:
                logger.warning(f"订阅 {code} 失败: {msg}")
        except Exception as exc:
            logger.error(f"订阅 {code} 异常: {exc}")

    async def _maybe_unsubscribe(self, code: str):
        if not self.quote_ctx or code not in self.subscribed_codes:
            return
        if self.code_sessions.get(code):
            return
        try:
            ret, msg = await asyncio.to_thread(self.quote_ctx.unsubscribe, code, self.subtypes)
            if ret == ft.RET_OK:
                self.subscribed_codes.discard(code)
                self.code_state.pop(code, None)
                await self._stop_kline_poll(code)
                logger.info(f"🛑 已取消订阅 {code}")
            else:
                logger.warning(f"取消订阅 {code} 失败: {msg}")
        except Exception as exc:
            logger.error(f"取消订阅 {code} 异常: {exc}")

    def update_state(self, code: str, kind: str, payload: Any):
        state = self.code_state[code]
        previous = state.get(kind)
        if self._is_same_payload(previous, payload, kind):
            return
        state[kind] = payload
        if kind == "kline" and self.kline_storage:
            try:
                records = payload if isinstance(payload, list) else [payload]
                self.kline_storage.save_batch(code, records)
            except Exception as exc:
                logger.debug(f"kline storage save failed: {exc}")
        if kind == "quote":
            self._log_quote_update(code, payload)
        self._broadcast(code)

    def _ensure_kline_poll(self, code: str):
        if code in self.kline_tasks or not self.quote_ctx:
            return
        task = self.loop.create_task(self._kline_poll_loop(code))
        self.kline_tasks[code] = task

    async def _stop_kline_poll(self, code: str):
        task = self.kline_tasks.pop(code, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.kline_latest_ts.pop(code, None)

    async def _kline_poll_loop(self, code: str):
        while code in self.subscribed_codes:
            try:
                ret, data = await asyncio.to_thread(
                    self.quote_ctx.get_cur_kline,
                    code,
                    240,
                    ft.KLType.K_1M,
                    ft.AuType.QFQ
                )
                if ret == ft.RET_OK:
                    records = _df_to_records(data)
                    if records:
                        latest_record = records[-1]
                        latest_ts = latest_record.get("time_key") or latest_record.get("time")
                        if latest_ts and self.kline_latest_ts.get(code) == latest_ts:
                            pass
                        else:
                            if latest_ts:
                                self.kline_latest_ts[code] = latest_ts
                            self.update_state(code, "kline", records)
                else:
                    logger.debug(f"get_cur_kline {code} ret={ret}")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"kline poll {code} error: {exc}")
            await asyncio.sleep(self.kline_poll_interval)

    async def ensure_code_subscription(self, code: str):
        await self._ensure_subscription(code)

    def start_guard(self):
        if self._guard_task or not self.quote_ctx:
            return
        self._guard_task = self.loop.create_task(self._subscription_guard())

    def _start_heartbeat(self):
        if self._heartbeat_task:
            return
        self._heartbeat_task = self.loop.create_task(self._heartbeat_loop())

    def _ensure_quote_ctx_started(self):
        if not self.quote_ctx or self._quote_ctx_started:
            return
        try:
            self.quote_ctx.start()
            self._quote_ctx_started = True
            logger.info("🚀 DashboardStreamManager 已启动富途推送线程")
        except Exception as exc:
            logger.error(f"启动富途推送线程失败: {exc}")

    async def _maybe_stop_guard(self):
        if self._guard_task and not self.code_sessions:
            self._guard_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._guard_task
            self._guard_task = None

    async def _subscription_guard(self):
        while True:
            try:
                codes = list(self.code_sessions.keys())
                for code in codes:
                    try:
                        await self._ensure_subscription(code)
                    except Exception as exc:
                        logger.warning(f"subscription guard ensure {code} failed: {exc}")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"subscription guard loop error: {exc}")
            await asyncio.sleep(self.guard_interval)

    def _compose_snapshot(self, code: str) -> Optional[Dict[str, Any]]:
        if code not in self.code_state:
            return None
        snapshot = {
            "code": code,
            "timestamp": datetime.now().isoformat()
        }
        snapshot.update(self.code_state[code])
        return snapshot

    async def _heartbeat_loop(self):
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                timestamp = datetime.now().isoformat()
                codes = list(self.code_sessions.keys())
                if not codes:
                    continue
                payload = {
                    "timestamp": timestamp,
                    "heartbeat": True
                }
                for code in codes:
                    self._broadcast_payload(code, payload)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug(f"heartbeat loop error: {exc}")

    def _broadcast(self, code: str):
        if code not in self.code_sessions:
            return
        snapshot = self._compose_snapshot(code)
        if not snapshot:
            return
        self._broadcast_payload(code, snapshot)

    def _broadcast_payload(self, code: str, payload: Dict[str, Any]):
        if code not in self.code_sessions:
            return
        now = time.time()
        last_log = self._broadcast_log_ts.get(code, 0)
        should_log = now - last_log > 2
        for session_id in list(self.code_sessions[code]):
            queue = self.session_queues.get(session_id)
            if not queue:
                continue
            message = dict(payload)
            message["code"] = code
            self.loop.call_soon_threadsafe(self._queue_put, queue, message)
            if should_log and self.debug_stream:
                logger.debug(
                    "[dashboard.stream.broadcast] code={} session={} payload_keys={} queue_size={}",
                    code,
                    session_id,
                    list(message.keys()),
                    queue.qsize() if hasattr(queue, "qsize") else "n/a",
                )
        if should_log:
            self._broadcast_log_ts[code] = now

    @staticmethod
    def _queue_put(queue: asyncio.Queue, payload: Dict[str, Any]):
        try:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass
        except Exception:
            pass

    def _log_quote_update(self, code: str, payload: Dict[str, Any]):
        now = time.time()
        last = self._quote_log_ts.get(code, 0)
        if now - last < 1:
            return
        self._quote_log_ts[code] = now
        price = payload.get("price")
        change = payload.get("change_rate")
        ts = payload.get("update_time")
        if self.debug_stream:
            logger.debug(
                "[dashboard.stream.quote] code={} price={} change_rate={} update_time={}",
                code,
                price,
                change,
                ts,
            )

    @staticmethod
    def _is_same_payload(previous: Any, current: Any, kind: str) -> bool:
        if previous is None:
            return False
        if kind == "quote" and isinstance(previous, dict) and isinstance(current, dict):
            keys = ("price", "change_rate", "update_time")
            return all(previous.get(k) == current.get(k) for k in keys)
        try:
            return previous == current
        except Exception:
            return False

    class StockQuoteHandler(ft.StockQuoteHandlerBase):
        def __init__(self, manager: "DashboardStreamManager"):
            super().__init__()
            self.manager = manager

        def on_recv_rsp(self, rsp_pb):
            ret, data = _extract_ret_data(super().on_recv_rsp(rsp_pb))
            if ret != ft.RET_OK or data is None:
                return ret, data
            for _, row in data.iterrows():
                code = row.get("code") or row.get("stock_code")
                if not code:
                    continue
                payload = {
                    "price": float(row.get("last_price") or row.get("price") or 0),
                    "change_rate": float(row.get("change_rate") or 0),
                    "volume": float(row.get("volume") or 0),
                    "turnover": float(row.get("turnover") or 0),
                    "update_time": row.get("update_time"),
                    "high": float(row.get("high_price") or row.get("high") or 0),
                    "low": float(row.get("low_price") or row.get("low") or 0),
                    "open": float(row.get("open_price") or row.get("open") or 0),
                    "close": float(row.get("last_price") or row.get("close") or 0),
                    "prev_close": float(row.get("prev_close_price") or row.get("prev_close") or 0),
                }
                self.manager.update_state(code, "quote", payload)
            return ret, data

    class OrderBookHandler(ft.OrderBookHandlerBase):
        def __init__(self, manager: "DashboardStreamManager"):
            super().__init__()
            self.manager = manager

        def on_recv_rsp(self, rsp_pb):
            ret, data = _extract_ret_data(super().on_recv_rsp(rsp_pb))
            if ret != ft.RET_OK or data is None:
                return ret, data
            records = _df_to_records(data)
            for record in records:
                code = record.get("code") or record.get("stock_code")
                if not code:
                    continue
                bids = record.get("Bid") or record.get("bid") or record.get("BidList") or []
                asks = record.get("Ask") or record.get("ask") or record.get("AskList") or []
                book = {
                    "bids": _normalize_levels(bids, top=10),
                    "asks": _normalize_levels(asks, top=10),
                    "timestamp": record.get("update_time") or record.get("time")
                }
                self.manager.update_state(code, "order_book", book)
            return ret, data

    class TickerHandler(ft.TickerHandlerBase):
        def __init__(self, manager: "DashboardStreamManager"):
            super().__init__()
            self.manager = manager

        def on_recv_rsp(self, rsp_pb):
            ret, data = _extract_ret_data(super().on_recv_rsp(rsp_pb))
            if ret != ft.RET_OK or data is None:
                return ret, data
            records = _df_to_records(data, limit=20)
            if not records:
                return ret, data
            code = records[0].get("code") or records[0].get("stock_code")
            if code:
                for item in records:
                    if "price" in item:
                        try:
                            item["price"] = float(item["price"])
                        except Exception:
                            pass
                self.manager.update_state(code, "ticker", records)
            return ret, data

    class BrokerHandler(ft.BrokerHandlerBase):
        def __init__(self, manager: "DashboardStreamManager"):
            super().__init__()
            self.manager = manager

        def on_recv_rsp(self, rsp_pb):
            ret, data = _extract_ret_data(super().on_recv_rsp(rsp_pb))
            if ret != ft.RET_OK or data is None:
                return ret, data
            records = _df_to_records(data)
            for record in records:
                code = record.get("code") or record.get("stock_code")
                if not code:
                    continue
                payload = {
                    "buyers": record.get("BidBrokerQueue") or record.get("Bid") or record.get("buyers") or [],
                    "sellers": record.get("AskBrokerQueue") or record.get("Ask") or record.get("sellers") or []
                }
                if not isinstance(payload["buyers"], list):
                    payload["buyers"] = []
                if not isinstance(payload["sellers"], list):
                    payload["sellers"] = []
                self.manager.update_state(code, "broker_queue", payload)
            return ret, data

    class RTDataHandler(ft.RTDataHandlerBase):
        def __init__(self, manager: "DashboardStreamManager"):
            super().__init__()
            self.manager = manager

        def on_recv_rsp(self, rsp_pb):
            ret, data = _extract_ret_data(super().on_recv_rsp(rsp_pb))
            if ret != ft.RET_OK or data is None:
                return ret, data
            records = _df_to_records(data, limit=180)
            if not records:
                return ret, data
            code = records[0].get("code") or records[0].get("stock_code")
            if code:
                for item in records:
                    price = item.get("price") or item.get("cur_price") or item.get("last_price")
                    try:
                        item["price"] = float(price)
                    except Exception:
                        pass
                self.manager.update_state(code, "rt_data", records)
            return ret, data

    class KLineHandler(ft.CurKlineHandlerBase):
        def __init__(self, manager: "DashboardStreamManager"):
            super().__init__()
            self.manager = manager

        def on_recv_rsp(self, rsp_pb):
            ret, data = _extract_ret_data(super().on_recv_rsp(rsp_pb))
            if ret != ft.RET_OK or data is None:
                return ret, data
            records = _df_to_records(data)
            if not records:
                return ret, data
            code = records[0].get("code") or records[0].get("stock_code")
            if code:
                for item in records:
                    close = item.get("close") or item.get("cur_price")
                    try:
                        item["close"] = float(close)
                    except Exception:
                        pass
                self.manager.update_state(code, "kline", records)
            return ret, data
def _extract_ret_data(result):
    if isinstance(result, tuple):
        if len(result) >= 2:
            return result[0], result[1]
        elif len(result) == 1:
            return result[0], None
    return result, None
