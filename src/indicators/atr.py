import pandas as pd
import numpy as np

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates the Average True Range (ATR) using Welles Wilder's smoothing.
    
    Args:
        high: High prices series.
        low: Low prices series.
        close: Close prices series.
        period: ATR window period (default 14).
        
    Returns:
        Pandas Series containing the ATR values.
    """
    if len(close) < period:
        return pd.Series(index=close.index, data=float('nan'))
        
    prev_close = close.shift(1)
    
    # True Range (TR) formula components
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    # Take the element-wise maximum
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    tr_vals = tr.fillna(0).values
    atr_vals = np.zeros_like(tr_vals, dtype=float)
    atr_vals[:period] = np.nan
    
    # Set the first valid window (index period) as standard simple average
    # Note: index 0 of TR is NaN due to shift(1), so we take TR from index 1 up to period (inclusive)
    atr_vals[period] = np.mean(tr_vals[1:period + 1])
    
    for idx in range(period + 1, len(close)):
        atr_vals[idx] = (atr_vals[idx - 1] * (period - 1) + tr_vals[idx]) / period
        
    return pd.Series(atr_vals, index=close.index)
