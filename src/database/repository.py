from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import Position, Trade, DailyBalanceHistory, StrategyState

class TradingRepository:
    """Handles async CRUD operations for all trading domain models using SQLAlchemy 2.0 style."""
    
    # --- POSITION OPERATIONS ---
    @staticmethod
    async def create_position(
        session: AsyncSession,
        symbol: str,
        strategy_name: str,
        qty: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop: Optional[float] = None
    ) -> Position:
        position = Position(
            symbol=symbol,
            strategy_name=strategy_name,
            qty=qty,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop,
            status="OPEN",
            entry_time=datetime.utcnow()
        )
        session.add(position)
        await session.flush()  # Populates position.id
        return position

    @staticmethod
    async def get_position_by_id(session: AsyncSession, position_id: int) -> Optional[Position]:
        result = await session.execute(select(Position).where(Position.id == position_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_open_positions(
        session: AsyncSession,
        strategy_name: Optional[str] = None
    ) -> List[Position]:
        query = select(Position).where(Position.status == "OPEN")
        if strategy_name:
            query = query.where(Position.strategy_name == strategy_name)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_closed_positions(
        session: AsyncSession,
        strategy_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Position]:
        query = select(Position).where(Position.status == "CLOSED").order_by(desc(Position.exit_time)).limit(limit)
        if strategy_name:
            query = query.where(Position.strategy_name == strategy_name)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def close_position(
        session: AsyncSession,
        position_id: int,
        exit_price: float,
        realized_pnl: float
    ) -> Optional[Position]:
        position = await TradingRepository.get_position_by_id(session, position_id)
        if position:
            position.status = "CLOSED"
            position.exit_price = exit_price
            position.exit_time = datetime.utcnow()
            position.realized_pnl = realized_pnl
            position.unrealized_pnl = 0.0
            session.add(position)
            await session.flush()
        return position

    @staticmethod
    async def update_position_pnl(
        session: AsyncSession,
        position_id: int,
        unrealized_pnl: float
    ) -> None:
        await session.execute(
            update(Position)
            .where(Position.id == position_id)
            .values(unrealized_pnl=unrealized_pnl)
        )

    @staticmethod
    async def update_position_stop_loss(
        session: AsyncSession,
        position_id: int,
        new_stop_loss: float
    ) -> None:
        await session.execute(
            update(Position)
            .where(Position.id == position_id)
            .values(stop_loss=new_stop_loss)
        )

    # --- TRADE OPERATIONS ---
    @staticmethod
    async def create_trade(
        session: AsyncSession,
        exchange_order_id: str,
        symbol: str,
        side: str,
        type_: str,
        price: float,
        qty: float,
        commission: float,
        strategy_name: str,
        position_id: Optional[int] = None
    ) -> Trade:
        trade = Trade(
            position_id=position_id,
            exchange_order_id=exchange_order_id,
            symbol=symbol,
            side=side.upper(),
            type=type_.upper(),
            price=price,
            qty=qty,
            commission=commission,
            strategy_name=strategy_name,
            timestamp=datetime.utcnow()
        )
        session.add(trade)
        await session.flush()
        return trade

    @staticmethod
    async def get_trade_history(
        session: AsyncSession,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        query = select(Trade).order_by(desc(Trade.timestamp)).limit(limit)
        if symbol:
            query = query.where(Trade.symbol == symbol)
        result = await session.execute(query)
        return list(result.scalars().all())

    # --- BALANCE HISTORY OPERATIONS ---
    @staticmethod
    async def create_daily_balance(
        session: AsyncSession,
        balance: float,
        equity: float,
        daily_drawdown: float = 0.0
    ) -> DailyBalanceHistory:
        history = DailyBalanceHistory(
            balance=balance,
            equity=equity,
            daily_drawdown=daily_drawdown,
            timestamp=datetime.utcnow()
        )
        session.add(history)
        await session.flush()
        return history

    @staticmethod
    async def get_daily_balance_history(
        session: AsyncSession,
        limit: int = 30
    ) -> List[DailyBalanceHistory]:
        result = await session.execute(
            select(DailyBalanceHistory)
            .order_by(desc(DailyBalanceHistory.timestamp))
            .limit(limit)
        )
        return list(result.scalars().all())

    # --- STRATEGY CONFIG STATE OPERATIONS ---
    @staticmethod
    async def get_strategy_state(
        session: AsyncSession,
        strategy_name: str
    ) -> Optional[StrategyState]:
        result = await session.execute(
            select(StrategyState).where(StrategyState.strategy_name == strategy_name)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save_or_update_strategy_state(
        session: AsyncSession,
        strategy_name: str,
        enabled: bool,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyState:
        state = await TradingRepository.get_strategy_state(session, strategy_name)
        if state:
            state.enabled = enabled
            if parameters is not None:
                state.parameters = parameters
        else:
            state = StrategyState(
                strategy_name=strategy_name,
                enabled=enabled,
                parameters=parameters or {}
            )
            session.add(state)
        await session.flush()
        return state
