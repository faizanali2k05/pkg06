import pandas as pd
from typing import Dict, Any, Optional
from src.strategies.base_strategy import BaseStrategy
from src.indicators.atr import calculate_atr
from src.indicators.volume import calculate_volume_sma
from src.core.logger import logger

class BreakoutStrategy(BaseStrategy):
    """
    Donchian Channel Breakout Strategy.
    
    Rules:
        Channel: 20-period Highest High of close prices.
        Entry:
            - Price breaks above the previous 20-period Highest High
            - Volume is above Volume SMA20
        Exit:
            - Initial Stop Loss: Entry - (2.0 * ATR14)
            - Take Profit: Entry + (2.0 * SL_distance) -> 1:2 Risk-Reward Ratio
    """

    def __init__(self, symbols: list, parameters: Optional[Dict[str, Any]] = None) -> None:
        default_params = {
            "channel_period": 20,
            "vol_period": 20,
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "rr_ratio": 2.0
        }
        if parameters:
            default_params.update(parameters)
            
        super().__init__(name="Channel_Breakout", symbols=symbols, parameters=default_params)

    def process_closed_candle(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        p = self.parameters
        
        # Warmup requirements
        warmup_required = p["channel_period"] + 5
        if len(df) < warmup_required:
            logger.debug(f"[{self.name}] {symbol} warming up ({len(df)}/{warmup_required} bars).")
            return None

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Calculate high channel bound of PREVIOUS N candles (excluding current candle to check crossover)
        # Shift(1) ensures we evaluate against the completed channel resistance
        channel_high = high.shift(1).rolling(window=p["channel_period"]).max()
        volume_sma = calculate_volume_sma(volume, p["vol_period"])
        atr = calculate_atr(high, low, close, p["atr_period"])

        curr_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        curr_high = high.iloc[-1]
        curr_volume = volume.iloc[-1]
        curr_vol_sma = volume_sma.iloc[-1]
        curr_atr = atr.iloc[-1]
        curr_channel_high = channel_high.iloc[-1]

        if pd.isna(curr_channel_high):
            return None

        # 1. Breakout condition: current close exceeds channel resistance, while previous close was below or equal
        breakout_ok = curr_close > curr_channel_high and prev_close <= curr_channel_high

        # 2. Volume volume verification
        volume_ok = curr_volume > curr_vol_sma

        logger.debug(
            f"[{self.name}] {symbol} evaluation -> Close: {curr_close:.2f}, Channel Resistance: {curr_channel_high:.2f}. "
            f"Breakout: {breakout_ok}, Volume Ok: {volume_ok} (Vol: {curr_volume:.0f} > SMA: {curr_vol_sma:.0f})"
        )

        if breakout_ok and volume_ok:
            logger.info(f"[{self.name}] BREAKOUT BUY SIGNAL triggered on {symbol} at {curr_close:.2f}")
            return {
                "strategy_name": self.name,
                "symbol": symbol,
                "action": "BUY",
                "price": curr_close,
                "atr": curr_atr,
                "parameters": {
                    "atr_multiplier": p["atr_multiplier"],
                    "rr_ratio": p["rr_ratio"]
                }
            }

        return None
