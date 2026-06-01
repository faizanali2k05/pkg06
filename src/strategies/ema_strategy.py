import pandas as pd
from typing import Dict, Any, Optional
from src.strategies.base_strategy import BaseStrategy
from src.indicators.ema import calculate_ema
from src.indicators.rsi import calculate_rsi
from src.indicators.atr import calculate_atr
from src.indicators.volume import calculate_volume_sma
from src.core.logger import logger

class EMAStrategy(BaseStrategy):
    """
    EMA Trend Pullback Trading Strategy V1.
    
    Rules:
        Trend Filter: EMA50 > EMA200
        Entry:
            - Low touches or dips below EMA20 (pullback)
            - Close price sustains above or within 1% of EMA20
            - RSI14 > 50 (momentum)
            - Volume > Volume SMA20 (participation)
        Exit:
            - Initial Stop Loss: Entry - (2.0 * ATR14)
            - Take Profit: Entry + (2.0 * SL_distance) -> 1:2 Risk-Reward Ratio
            - Trailing Stop: Support enabled via ATR distance
    """

    def __init__(self, symbols: list, parameters: Optional[Dict[str, Any]] = None) -> None:
        default_params = {
            "ema_fast": 20,
            "ema_trend_filter": 50,
            "ema_trend_base": 200,
            "rsi_period": 14,
            "rsi_threshold": 50.0,
            "vol_period": 20,
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "rr_ratio": 2.0
        }
        if parameters:
            default_params.update(parameters)
            
        super().__init__(name="EMA_Trend_Pullback", symbols=symbols, parameters=default_params)

    def process_closed_candle(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        p = self.parameters
        
        # Ensure sufficient history is present for EMA200 calculation
        warmup_required = p["ema_trend_base"] + 15
        if len(df) < warmup_required:
            logger.debug(f"[{self.name}] {symbol} warming up ({len(df)}/{warmup_required} bars).")
            return None

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Run vector computations on series
        ema20 = calculate_ema(close, p["ema_fast"])
        ema50 = calculate_ema(close, p["ema_trend_filter"])
        ema200 = calculate_ema(close, p["ema_trend_base"])
        rsi = calculate_rsi(close, p["rsi_period"])
        atr = calculate_atr(high, low, close, p["atr_period"])
        volume_sma = calculate_volume_sma(volume, p["vol_period"])

        # Fetch last elements
        curr_close = close.iloc[-1]
        curr_low = low.iloc[-1]
        curr_ema20 = ema20.iloc[-1]
        curr_ema50 = ema50.iloc[-1]
        curr_ema200 = ema200.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_atr = atr.iloc[-1]
        curr_volume = volume.iloc[-1]
        curr_vol_sma = volume_sma.iloc[-1]

        # 1. Trend Filter: EMA50 must be strictly above EMA200 (bull market filter)
        trend_ok = curr_ema50 > curr_ema200

        # 2. Pullback Filter: Candle low crosses below EMA20, but closes above 99% of EMA20
        pullback_ok = curr_low <= curr_ema20 and curr_close >= (curr_ema20 * 0.99)

        # 3. Momentum Filter: RSI is above 50
        rsi_ok = curr_rsi > p["rsi_threshold"]

        # 4. Volume Confirmation: Volume is above average volume of 20 periods
        volume_ok = curr_volume > curr_vol_sma

        logger.debug(
            f"[{self.name}] {symbol} indicators -> Close: {curr_close:.2f}, Low: {curr_low:.2f}. "
            f"EMA20: {curr_ema20:.2f}, EMA50: {curr_ema50:.2f}, EMA200: {curr_ema200:.2f}. "
            f"RSI: {curr_rsi:.1f}, Volume: {curr_volume:.0f} (SMA: {curr_vol_sma:.0f}). "
            f"Checks -> Trend: {trend_ok}, Pullback: {pullback_ok}, RSI: {rsi_ok}, Vol: {volume_ok}"
        )

        # Triggers entry if all conditions align
        if trend_ok and pullback_ok and rsi_ok and volume_ok:
            logger.info(f"[{self.name}] ENTRY BUY SIGNAL triggered on {symbol} at {curr_close:.2f}")
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
