import asyncio
import json
import websockets
from typing import Callable, Dict, List, Optional, Any
from src.core.logger import logger
from src.core.config import settings

class BinanceWebSocketManager:
    """Manages active WebSocket connections to public Binance stream feeds, routing events to registered strategy layers."""

    def __init__(self) -> None:
        self.callbacks: Dict[str, List[Callable[[Dict[str, Any]], Any]]] = {}
        # Convert standard BTC/USDT to raw lower address btcusdt for sockets
        self.symbols: List[str] = [sym.lower().replace("/", "") for sym in settings.TRADING_SYMBOLS]
        self.timeframe: str = "1m"
        self.running: bool = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task] = None

    def register_callback(self, event_type: str, callback: Callable[[Dict[str, Any]], Any]) -> None:
        """
        Registers an async callback trigger.
        
        Args:
            event_type: The stream class (e.g. 'kline').
            callback: Async function to process raw JSON payload.
        """
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)
        logger.info(f"Registered WebSocket callback for '{event_type}' events.")

    async def start(self) -> None:
        """Launches the WebSocket worker listener loop."""
        self.running = True
        self._listen_task = asyncio.create_task(self._connect_and_listen_loop())
        logger.info("Started Binance WebSocket connection manager.")

    async def stop(self) -> None:
        """Tears down live WebSocket processes and sockets."""
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

    async def _connect_and_listen_loop(self) -> None:
        # Construct multiplexed stream parameter URL
        streams = [f"{sym}@kline_{self.timeframe}" for sym in self.symbols]
        streams_query = "/".join(streams)
        
        ws_url = f"wss://stream.binance.com:9443/stream?streams={streams_query}"
        
        while self.running:
            try:
                logger.info(f"Connecting to Binance public stream socket: {ws_url}")
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                    self.websocket = ws
                    logger.info("Connection established. Subscriptions loaded.")
                    
                    while self.running:
                        try:
                            raw_msg = await ws.recv()
                            payload = json.loads(raw_msg)
                            
                            # Extrapolate internal stream type
                            stream_name = payload.get("stream", "")
                            data = payload.get("data", {})
                            
                            if "@kline_" in stream_name:
                                # Dispatch update task concurrently to prevent processing bottlenecks
                                for cb in self.callbacks.get("kline", []):
                                    asyncio.create_task(self._safe_execute_callback(cb, data))
                                    
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("Binance websocket server closed connection unexpectedly.")
                            break
                        except Exception as e:
                            logger.error(f"Error handling socket frame payload: {e}")
            except Exception as e:
                if self.running:
                    logger.error(f"WebSocket socket client exception: {e}. Restoring link in 5 seconds.")
                    await asyncio.sleep(5)

    async def _safe_execute_callback(
        self,
        callback: Callable[[Dict[str, Any]], Any],
        data: Dict[str, Any]
    ) -> None:
        try:
            await callback(data)
        except Exception as e:
            logger.error(f"Unhandled callback error in websocket dispatcher: {e}")
