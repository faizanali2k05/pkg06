from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

from src.core.config import settings
from src.core.logger import logger

MarketCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class BinanceWebSocketManager:
    """Multiplexes Binance public streams and normalizes payloads for the engine."""

    def __init__(self, symbols: list[str] | None = None, timeframe: str | None = None) -> None:
        self.symbols = symbols or settings.TRADING_SYMBOLS
        self.timeframe = timeframe or settings.BINANCE_WS_TIMEFRAME
        self.callbacks: dict[str, list[MarketCallback]] = {
            "kline": [],
            "ticker": [],
            "order_book": [],
        }
        self.running = False
        self.websocket: websockets.WebSocketClientProtocol | None = None
        self._listen_task: asyncio.Task[None] | None = None
        self._symbol_lookup = {
            symbol.replace("/", "").upper(): symbol for symbol in self.symbols
        }

    def register_callback(self, event_type: str, callback: MarketCallback) -> None:
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)
        logger.info("Registered WebSocket callback for '%s' events.", event_type)

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._listen_task = asyncio.create_task(self._connect_and_listen_loop())
        logger.info("Started Binance WebSocket connection manager.")

    async def stop(self) -> None:
        self.running = False
        if self.websocket:
            await self.websocket.close()
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped Binance WebSocket connection manager.")

    def _build_ws_url(self) -> str:
        streams: list[str] = []
        depth = settings.ORDER_BOOK_DEPTH
        for symbol in self.symbols:
            raw = symbol.lower().replace("/", "")
            streams.append(f"{raw}@kline_{self.timeframe}")
            streams.append(f"{raw}@ticker")
            streams.append(f"{raw}@depth{depth}@100ms")
        return f"{settings.BINANCE_WS_BASE_URL}?streams={'/'.join(streams)}"

    async def _connect_and_listen_loop(self) -> None:
        ws_url = self._build_ws_url()
        reconnect_delay = 1.0

        while self.running:
            try:
                logger.info("Connecting to Binance WebSocket stream.")
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                    self.websocket = ws
                    reconnect_delay = 1.0
                    logger.info("Binance WebSocket connection established.")

                    async for raw_msg in ws:
                        if not self.running:
                            break
                        await self._handle_raw_message(raw_msg)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self.running:
                    logger.error(
                        "WebSocket connection failed: %s. Reconnecting in %.1f seconds.",
                        exc,
                        reconnect_delay,
                    )
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 60.0)

    async def _handle_raw_message(self, raw_msg: str) -> None:
        try:
            payload = json.loads(raw_msg)
        except json.JSONDecodeError as exc:
            logger.warning("Ignoring malformed WebSocket payload: %s", exc)
            return

        stream_name = payload.get("stream", "")
        data = payload.get("data", {})
        event_type, symbol, normalized = self._normalize_event(stream_name, data)
        if event_type is None or symbol is None or normalized is None:
            return

        for callback in self.callbacks.get(event_type, []):
            asyncio.create_task(self._safe_execute_callback(callback, symbol, normalized))

    def _normalize_event(
        self,
        stream_name: str,
        data: dict[str, Any],
    ) -> tuple[str | None, str | None, dict[str, Any] | None]:
        raw_symbol = str(data.get("s") or stream_name.split("@", 1)[0]).upper()
        symbol = self._symbol_lookup.get(raw_symbol, raw_symbol)

        if "@kline_" in stream_name:
            kline = data.get("k", {})
            return "kline", symbol, {
                "event_time": data.get("E"),
                "t": kline.get("t"),
                "T": kline.get("T"),
                "o": kline.get("o"),
                "h": kline.get("h"),
                "l": kline.get("l"),
                "c": kline.get("c"),
                "v": kline.get("v"),
                "closed": bool(kline.get("x")),
                "timeframe": kline.get("i", self.timeframe),
            }

        if "@ticker" in stream_name:
            return "ticker", symbol, {
                "event_time": data.get("E"),
                "bid": data.get("b"),
                "ask": data.get("a"),
                "last": data.get("c"),
                "quote_volume": data.get("q"),
                "price_change_pct": data.get("P"),
            }

        if "@depth" in stream_name:
            return "order_book", symbol, {
                "event_time": data.get("E"),
                "first_update_id": data.get("U"),
                "final_update_id": data.get("u"),
                "bids": data.get("b", []),
                "asks": data.get("a", []),
            }

        return None, None, None

    async def _safe_execute_callback(
        self,
        callback: MarketCallback,
        symbol: str,
        data: dict[str, Any],
    ) -> None:
        try:
            result = callback(symbol, data)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.exception("Unhandled callback error in WebSocket dispatcher: %s", exc)
