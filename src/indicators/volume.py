import pandas as pd

def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculates the Simple Moving Average (SMA) of the trade volume.
    
    Args:
        volume: Volume series.
        period: Volume SMA window period (default 20).
        
    Returns:
        Pandas Series containing the volume SMA values.
    """
    if len(volume) < period:
        return pd.Series(index=volume.index, data=float('nan'))
        
    return volume.rolling(window=period, min_periods=period).mean()
