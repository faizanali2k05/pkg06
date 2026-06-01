from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Any, Optional
from src.core.logger import logger

class BaseStrategy(ABC):
    """Abstract Base Class for all ApexQuant strategies, managing historical price windows and tick streaming."""

    def __init__(self, name: str, symbols: List[str], parameters: Optional[Dict[str, Any]] = None) -> None:
        self.name: str = name
        self.symbols: List[str] = symbols
        self.parameters: Dict[str, Any] = parameters or {}
        self.historical_data: Dict[str, pd.DataFrame] = {}  # Indexed by symbol
        self.enabled: bool = True

    def update_parameters(self, params: Dict[str, Any]) -> None:
        """Dynamically adjusts strategy settings without requiring service restarts."""
        self.parameters.update(params)
        logger.info(f"[{self.name}] Applied runtime parameter changes: {params}")

    def on_historical_candles(self, symbol: str, df: pd.DataFrame) -> None:
        """Feeds historical data into strategy buffers for indicator warm-ups."""
        self.historical_data[symbol] = df.copy()
        logger.debug(f"[{self.name}] Warmed up with {len(df)} candles for {symbol}.")

    def on_tick(self, symbol: str, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Receives WebSocket streaming tick updates, adjusts active candle, and triggers trade analysis.
        
        Args:
            symbol: Ticker symbol (e.g. BTC/USDT).
            tick: Live candle payload.
            
        Returns:
            Optional[Dict]: Signal details if trade criteria match, otherwise None.
        """
        if not self.enabled:
            return None

        if symbol not in self.historical_data:
            self.historical_data[symbol] = pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            )

        df = self.historical_data[symbol]
        timestamp = pd.to_datetime(tick["t"], unit="ms")

        # Update running candle or append completed kline
        if not df.empty and df.index[-1] == timestamp:
            df.loc[timestamp] = [
                float(tick["o"]),
                float(tick["h"]),
                float(tick["l"]),
                float(tick["c"]),
                float(tick["v"])
            ]
        else:
            new_row = pd.DataFrame(
                [[float(tick["o"]), float(tick["h"]), float(tick["l"]), float(tick["c"]), float(tick["v"])]],
                columns=["open", "high", "low", "close", "volume"],
                index=[timestamp]
            )
            df = pd.concat([df, new_row])

        # Prevent memory exhaustion by trimming historical buffers
        max_limit = 500
        if len(df) > max_limit:
            df = df.iloc[-max_limit:]

        self.historical_data[symbol] = df

        # Execute signals only on complete candle closure to prevent premature entries (whipsaws)
        if tick.get("closed", False):
            return self.process_closed_candle(symbol, df)

        return None

    @abstractmethod
    def process_closed_candle(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Invoked immediately upon candlestick closure. Overridden by child classes."""
        pass
