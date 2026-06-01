from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.exchange.binance_client import BinanceClient
from src.database.repository import TradingRepository
from src.core.logger import logger
from src.core.exceptions import OrderExecutionError
from src.database.models import Position, Trade

class OrderExecutor:
    """Manages raw order entry/exit loops, commission calculations, PnL reports, and SQL integrations."""

    def __init__(self, binance_client: BinanceClient) -> None:
        self.client = binance_client

    async def execute_entry(
        self,
        db_session: AsyncSession,
        symbol: str,
        strategy_name: str,
        side: str,
        qty: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Position:
        """
        Executes a market entry order, saves the resulting Position database entry, 
        and audits execution into the Trades log.
        """
        try:
            logger.info(f"Dispatching entry {side.upper()} market order for {symbol} (qty: {qty:.6f})")
            
            # Place entry order on exchange (using market orders for guaranteed execution in dry/live runs)
            order = await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="market",
                qty=qty,
                price=price
            )

            fill_price = order.get("price") or price
            execution_qty = order.get("amount") or qty
            order_id = order.get("id", "unknown_order")
            fee = order.get("fee", {}).get("cost", 0.0)

            # Persist position in database
            position = await TradingRepository.create_position(
                session=db_session,
                symbol=symbol,
                strategy_name=strategy_name,
                qty=execution_qty,
                entry_price=fill_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            # Create corresponding trade record
            trade = await TradingRepository.create_trade(
                session=db_session,
                exchange_order_id=order_id,
                symbol=symbol,
                side=side,
                type_="market",
                price=fill_price,
                qty=execution_qty,
                commission=fee,
                strategy_name=strategy_name,
                position_id=position.id
            )

            # Proactively trigger notification system dynamically to avoid circular import issues
            try:
                from src.notifications.alert_manager import alert_manager
                alert_manager.trigger_trade_alert(trade, position)
            except Exception as notify_err:
                logger.error(f"Failed to dispatch trade alert notification: {notify_err}")

            logger.info(f"Entry filled successfully. Position ID: {position.id}, Order ID: {order_id}")
            return position

        except Exception as e:
            logger.error(f"Execution engine failed to open position on {symbol}: {e}")
            raise OrderExecutionError(f"Entry order placement failed: {e}")

    async def execute_exit(
        self,
        db_session: AsyncSession,
        position_id: int,
        exit_price: float,
        reason: str = "Exit Signal"
    ) -> Optional[Position]:
        """
        Executes a market exit order, marks the Position status as CLOSED,
        updates realized PnL records, and logs the closing Trade history.
        """
        position = await TradingRepository.get_position_by_id(db_session, position_id)
        if not position or position.status != "OPEN":
            logger.warning(f"Abort exit command: Position {position_id} not found or already closed.")
            return None

        symbol = position.symbol
        qty = position.qty
        
        # Spot: Close a long position by selling
        side = "SELL"

        try:
            logger.info(f"Dispatching exit market order to CLOSE position {position_id} ({symbol}). Reason: {reason}")
            
            # Place exit order on exchange
            order = await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="market",
                qty=qty,
                price=exit_price
            )

            fill_price = order.get("price") or exit_price
            execution_qty = order.get("amount") or qty
            order_id = order.get("id", "unknown_order")
            fee = order.get("fee", {}).get("cost", 0.0)

            # Calculate realized PnL (Spot Standard Long execution)
            realized_pnl = (fill_price - position.entry_price) * execution_qty

            # Close position entry in SQL
            closed_pos = await TradingRepository.close_position(
                session=db_session,
                position_id=position.id,
                exit_price=fill_price,
                realized_pnl=realized_pnl
            )

            # Log corresponding exit trade
            trade = await TradingRepository.create_trade(
                session=db_session,
                exchange_order_id=order_id,
                symbol=symbol,
                side=side,
                type_="market",
                price=fill_price,
                qty=execution_qty,
                commission=fee,
                strategy_name=position.strategy_name,
                position_id=position.id
            )

            # Dispatch notification
            try:
                from src.notifications.alert_manager import alert_manager
                alert_manager.trigger_trade_alert(trade, closed_pos)
            except Exception as notify_err:
                logger.error(f"Failed to dispatch trade alert notification: {notify_err}")

            logger.info(
                f"Exit filled successfully. Position ID: {position.id} closed. "
                f"Realized PnL: {realized_pnl:.4f}. Order ID: {order_id}"
            )
            return closed_pos

        except Exception as e:
            logger.error(f"Execution engine failed to close position {position_id} on {symbol}: {e}")
            raise OrderExecutionError(f"Exit order placement failed: {e}")
