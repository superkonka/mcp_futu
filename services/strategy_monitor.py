import asyncio
from typing import Dict, Any, Optional

from loguru import logger

from models.futu_models import StockQuoteRequest
from services.recommendation_storage import RecommendationStorageService
from services.futu_service import FutuService


class StrategyMonitorService:
    def __init__(
        self,
        futu_service: FutuService,
        storage: RecommendationStorageService,
    ):
        self.futu_service = futu_service
        self.storage = storage
        self._tasks: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        running = await asyncio.to_thread(self.storage.list_running_strategies)
        for strategy in running:
            await self.register_strategy(strategy)
        logger.info(f"Strategy monitor loaded {len(running)} running strategies")

    async def stop(self):
        self._running = False
        async with self._lock:
            for task in self._tasks.values():
                task.cancel()
            self._tasks.clear()

    async def register_strategy(self, strategy: Dict[str, Any]):
        if not strategy.get("id"):
            return
        strategy_id = int(strategy["id"])
        async with self._lock:
            if task := self._tasks.get(strategy_id):
                task.cancel()
            task = asyncio.create_task(self._watch_strategy(strategy))
            self._tasks[strategy_id] = task

    async def unregister_strategy(self, strategy_id: int):
        async with self._lock:
            task = self._tasks.pop(strategy_id, None)
            if task:
                task.cancel()

    async def _watch_strategy(self, strategy: Dict[str, Any]):
        strategy_id = int(strategy["id"])
        code = strategy["code"]
        entry_price = strategy.get("entry_price")
        target_price = strategy.get("target_price")
        stop_loss = strategy.get("stop_loss")
        monitor_config = strategy.get("monitor_config") or {}
        price_interval = float(monitor_config.get("price_interval", 60))
        fundamental_interval = float(monitor_config.get("fundamental_interval", 1800))
        enable_fundamental = bool(monitor_config.get("enable_fundamental", False))
        last_fundamental_check: Optional[float] = None
        logger.info(f"[monitor] start strategy={strategy_id} code={code}")
        try:
            while self._running:
                try:
                    quote_resp = await self.futu_service.get_stock_quote(
                        StockQuoteRequest(code_list=[code])
                    )
                    price = None
                    if quote_resp.ret_code == 0 and quote_resp.data:
                        quotes = quote_resp.data.get("quotes") or []
                        if quotes:
                            price = quotes[0].get("cur_price") or quotes[0].get("last_price")
                    if price is not None:
                        await self._check_price_triggers(strategy, float(price), entry_price, target_price, stop_loss)
                except Exception as exc:
                    logger.warning(f"[monitor] price check failed for {code}: {exc}")
                if enable_fundamental:
                    now = asyncio.get_event_loop().time()
                    if (last_fundamental_check is None) or (now - last_fundamental_check > fundamental_interval):
                        last_fundamental_check = now
                        await self._emit_alert(
                            strategy_id,
                            code,
                            "fundamental_refresh",
                            "触发基本面增量检查",
                            level="info",
                            payload={"note": "Need to fetch latest fundamental news"},
                        )
                await asyncio.sleep(price_interval)
        except asyncio.CancelledError:
            logger.info(f"[monitor] stop strategy={strategy_id} code={code}")
        except Exception as exc:
            logger.error(f"[monitor] unexpected error for {strategy_id}: {exc}")

    async def _check_price_triggers(
        self,
        strategy: Dict[str, Any],
        current_price: float,
        entry_price: Optional[float],
        target_price: Optional[float],
        stop_loss: Optional[float],
    ):
        strategy_id = int(strategy["id"])
        code = strategy["code"]
        if target_price is not None and current_price >= float(target_price):
            await self._emit_alert(
                strategy_id,
                code,
                "target_hit",
                f"价格触达目标价 {target_price}",
                level="success",
                payload={"current_price": current_price, "target_price": target_price},
            )
        if stop_loss is not None and current_price <= float(stop_loss):
            await self._emit_alert(
                strategy_id,
                code,
                "stop_loss",
                f"价格跌破止损 {stop_loss}",
                level="danger",
                payload={"current_price": current_price, "stop_loss": stop_loss},
            )
        if entry_price is not None:
            diff = current_price - float(entry_price)
            pct = diff / float(entry_price) if entry_price else 0
            await self._emit_alert(
                strategy_id,
                code,
                "price_update",
                f"最新价格 {current_price:.3f} ({pct*100:.2f}% vs entry)",
                level="info",
                payload={"current_price": current_price, "entry_price": entry_price, "change_pct": pct},
            )

    async def _emit_alert(
        self,
        strategy_id: int,
        code: str,
        alert_type: str,
        message: str,
        *,
        level: str = "info",
        payload: Optional[Dict[str, Any]] = None,
    ):
        await asyncio.to_thread(
            self.storage.add_alert,
            strategy_id,
            code,
            alert_type,
            message,
            level,
            payload,
        )
        logger.info(f"[monitor] {alert_type} strategy={strategy_id} msg={message}")
