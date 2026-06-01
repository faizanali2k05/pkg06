import pandas as pd

try:
    import talib
except ImportError:  # pragma: no cover - optional production acceleration
    talib = None

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    Calculates the Exponential Moving Average (EMA) of a Pandas Series.
    
    Args:
        series: Close prices series.
        period: Number of periods for EMA.
        
    Returns:
        Pandas Series containing the EMA values.
    """
    if len(series) < period:
        # Return NaN series if there is not enough historical data
        return pd.Series(index=series.index, data=float('nan'))
        
    if talib is not None:
        return pd.Series(talib.EMA(series.astype(float).to_numpy(), timeperiod=period), index=series.index)

    return series.ewm(span=period, adjust=False).mean()
