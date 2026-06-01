import pandas as pd
import numpy as np

try:
    import talib
except ImportError:  # pragma: no cover - optional production acceleration
    talib = None

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI) of a Pandas Series using Wilder's smoothing.
    
    Args:
        series: Close prices series.
        period: RSI window period (default 14).
        
    Returns:
        Pandas Series containing the RSI values.
    """
    if len(series) < period:
        return pd.Series(index=series.index, data=float('nan'))

    if talib is not None:
        return pd.Series(talib.RSI(series.astype(float).to_numpy(), timeperiod=period), index=series.index)
        
    delta = series.diff()
    gain = (delta.clip(lower=0)).fillna(0)
    loss = (-delta.clip(upper=0)).fillna(0)
    
    gain_vals = gain.values
    loss_vals = loss.values
    
    # Welles Wilder smoothing via high-performance iteration
    wilder_gains = np.zeros_like(gain_vals, dtype=float)
    wilder_losses = np.zeros_like(loss_vals, dtype=float)
    
    wilder_gains[:period] = np.nan
    wilder_losses[:period] = np.nan
    
    # Set the first valid window (index period) as standard simple average
    # Note: index 0 of delta is NaN, so we take gains from index 1 up to period (inclusive)
    wilder_gains[period] = np.mean(gain_vals[1:period + 1])
    wilder_losses[period] = np.mean(loss_vals[1:period + 1])
    
    for idx in range(period + 1, len(series)):
        wilder_gains[idx] = (wilder_gains[idx - 1] * (period - 1) + gain_vals[idx]) / period
        wilder_losses[idx] = (wilder_losses[idx - 1] * (period - 1) + loss_vals[idx]) / period
        
    # Prevent divide by zero
    rs = wilder_gains / np.where(wilder_losses == 0, 1e-10, wilder_losses)
    rsi = 100 - (100 / (1 + rs))
    rsi[:period] = np.nan
    
    return pd.Series(rsi, index=series.index)
