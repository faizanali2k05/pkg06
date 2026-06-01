from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config import settings
from src.core.logger import logger
from src.core.exceptions import RiskLimitExceeded
from src.database.repository import TradingRepository

class RiskManager:
    """Enforces absolute risk boundaries before trade executions, blocking overrides if limits are violated."""

    @staticmethod
    async def validate_order(
        db_session: AsyncSession,
        symbol: str,
        current_equity: float,
        proposed_cost: float
    ) -> bool:
        """
        Validates the proposed trade order against active risk constraints.
        
        Args:
            db_session: Active database session.
            symbol: Target symbol.
            current_equity: Current total account valuation.
            proposed_cost: Expected value of the new position.
            
        Returns:
            bool: True if order is approved.
            
        Raises:
            RiskLimitExceeded: If any risk constraints are breached.
        """
        # 1. Enforce Maximum Simultaneous Positions
        open_positions = await TradingRepository.get_open_positions(db_session)
        
        # If the asset is already open, it is an adjustment/exit, which is allowed.
        # But if it's a new asset and we are already at capacity, block it.
        is_already_open = any(pos.symbol == symbol for pos in open_positions)
        
        if not is_already_open and len(open_positions) >= settings.MAX_OPEN_POSITIONS:
            msg = f"Order blocked: Active positions ({len(open_positions)}) meet capacity threshold ({settings.MAX_OPEN_POSITIONS})."
            logger.warning(msg)
            raise RiskLimitExceeded(msg, limit_type="max_positions")

        # 2. Check Daily Drawdown Protection
        balance_history = await TradingRepository.get_daily_balance_history(db_session, limit=1)
        
        if balance_history:
            starting_daily_equity = balance_history[0].equity
            # Avoid divide-by-zero
            if starting_daily_equity > 0:
                drawdown = (starting_daily_equity - current_equity) / starting_daily_equity
                
                if drawdown >= settings.DAILY_DRAWDOWN_LIMIT_PCT:
                    msg = (
                        f"Order blocked: Daily drawdown ({drawdown * 100:.2f}%) exceeds "
                        f"limit boundary ({settings.DAILY_DRAWDOWN_LIMIT_PCT * 100:.1f}%). "
                        f"Start of Day Equity: {starting_daily_equity:.2f} USDT, Current: {current_equity:.2f} USDT"
                    )
                    logger.critical(msg)
                    raise RiskLimitExceeded(msg, limit_type="daily_drawdown")
        
        logger.info(f"Risk checks passed. Order approved for {symbol}.")
        return True
