import pandas as pd

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
        
    return series.ewm(span=period, adjust=False).mean()
