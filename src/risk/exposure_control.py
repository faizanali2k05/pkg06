from typing import List
from src.core.logger import logger
from src.database.models import Position

def check_exposure_limit(
    open_positions: List[Position],
    proposed_symbol: str,
    proposed_cost: float,
    account_equity: float,
    max_single_asset_exposure: float = 0.50  # Cap concentration to 50% of equity per coin
) -> bool:
    """
    Validates capital allocation concentrations to prevent over-exposure to a single asset.
    
    Args:
        open_positions: Active open positions.
        proposed_symbol: Coin ticker being evaluated.
        proposed_cost: Cost size of the new position.
        account_equity: Total account equity.
        max_single_asset_exposure: Max percentage of equity allocated to one asset (default 50%).
        
    Returns:
        bool: True if exposure limits are respected, otherwise False.
    """
    if account_equity <= 0:
        return False
        
    # Sum current cost allocations for the target asset
    active_exposure = 0.0
    for pos in open_positions:
        if pos.symbol == proposed_symbol:
            active_exposure += (pos.qty * pos.entry_price)
            
    total_proposed_exposure = active_exposure + proposed_cost
    exposure_pct = total_proposed_exposure / account_equity
    
    if exposure_pct > max_single_asset_exposure:
        logger.warning(
            f"Exposure limit rejected: Proposed exposure for {proposed_symbol} is "
            f"{exposure_pct * 100:.1f}% of equity, which exceeds maximum single asset limit "
            f"({max_single_asset_exposure * 100:.1f}%)."
        )
        return False
        
    logger.debug(
        f"Exposure control passed: {proposed_symbol} allocation represents {exposure_pct * 100:.1f}% "
        f"of total account equity."
    )
    return True
