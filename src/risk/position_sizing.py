from src.core.logger import logger
from src.core.config import settings

def calculate_position_size(
    account_equity: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = None
) -> float:
    """
    Calculates position size (quantity) based on a fixed risk percentage of account equity.
    
    Formula:
        Risk Amount = Equity * Risk Percentage
        Risk per unit = |Entry Price - Stop Loss Price|
        Position Size = Risk Amount / Risk per unit
        
    Args:
        account_equity: Total value of capital (cash + open positions).
        entry_price: The expected price of entry.
        stop_loss_price: The stop loss level price.
        risk_pct: Target risk percentage per trade (default from settings: 1%).
        
    Returns:
        The calculated trade quantity (float).
    """
    if risk_pct is None:
        risk_pct = settings.RISK_PERCENT_PER_TRADE
        
    if entry_price <= 0 or stop_loss_price <= 0:
        logger.error(f"Invalid pricing for position sizing: Entry={entry_price}, SL={stop_loss_price}")
        return 0.0
        
    risk_per_unit = abs(entry_price - stop_loss_price)
    
    if risk_per_unit == 0:
        logger.warning("Stop loss price is identical to entry price. Sizing defaulted to 0.")
        return 0.0
        
    risk_amount = account_equity * risk_pct
    qty = risk_amount / risk_per_unit
    
    # Capital safeguard: Cost of purchase cannot exceed equity
    cost = qty * entry_price
    if cost > account_equity:
        logger.warning(
            f"Calculated trade cost ({cost:.2f} USDT) exceeds account equity ({account_equity:.2f} USDT). "
            f"Clipping size to maximum equity capability."
        )
        qty = account_equity / entry_price
        
    logger.info(
        f"Position Sizing - Equity: {account_equity:.2f} USDT, Risk Amount: {risk_amount:.2f} USDT ({(risk_pct * 100):.1f}%), "
        f"Risk/Unit: {risk_per_unit:.4f}, Calculated Qty: {qty:.6f} (Cost: {(qty * entry_price):.2f} USDT)"
    )
    return qty
