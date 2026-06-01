from typing import Tuple
from src.core.logger import logger

def calculate_sl_tp(
    entry_price: float,
    atr_val: float,
    atr_multiplier: float = 2.0,
    rr_ratio: float = 2.0
) -> Tuple[float, float]:
    """
    Calculates initial ATR-based Stop Loss and Take Profit levels.
    
    Args:
        entry_price: The trade entry price.
        atr_val: Current ATR value of the asset.
        atr_multiplier: Number of ATRs to risk (default 2.0).
        rr_ratio: Target Risk-to-Reward ratio (default 2.0, representing 1:2).
        
    Returns:
        Tuple[stop_loss_price, take_profit_price]
    """
    if atr_val <= 0:
        logger.warning(f"ATR value is zero or negative ({atr_val}). Defaulting to 2% fixed distance SL.")
        # Fallback to 2% SL if ATR is not loaded/invalid
        stop_loss = entry_price * 0.98
    else:
        stop_loss = entry_price - (atr_val * atr_multiplier)
        
    risk_distance = entry_price - stop_loss
    take_profit = entry_price + (risk_distance * rr_ratio)
    
    logger.debug(
        f"StopLoss/TakeProfit - Entry: {entry_price:.4f}, ATR: {atr_val:.4f}, "
        f"SL: {stop_loss:.4f} (-{((entry_price - stop_loss) / entry_price * 100):.2f}%), "
        f"TP: {take_profit:.4f} (+{((take_profit - entry_price) / entry_price * 100):.2f}%)"
    )
    return stop_loss, take_profit

def update_trailing_stop(
    current_price: float,
    current_stop_loss: float,
    atr_val: float,
    atr_multiplier: float = 2.0
) -> float:
    """
    Calculates new trailing stop loss level based on current price rise.
    Stop loss only moves UP for long positions, never down.
    
    Args:
        current_price: Active market price.
        current_stop_loss: Current active stop loss price.
        atr_val: Active ATR value.
        atr_multiplier: ATR multiplier to determine trailing distance.
        
    Returns:
        The updated stop-loss price (float).
    """
    if atr_val <= 0:
        return current_stop_loss
        
    calculated_sl = current_price - (atr_val * atr_multiplier)
    
    # Standard trailing logic: only move SL higher
    if calculated_sl > current_stop_loss:
        logger.debug(f"Trailing SL adjusted higher from {current_stop_loss:.4f} to {calculated_sl:.4f}")
        return calculated_sl
        
    return current_stop_loss
