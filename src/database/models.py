from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from src.database.session import Base

class Position(Base):
    """Tracks active and closed trades. Acts as aggregate root for trade entries."""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    strategy_name = Column(String, nullable=False, index=True)
    qty = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    entry_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    status = Column(String, default="OPEN", nullable=False, index=True)  # OPEN, CLOSED
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    trailing_stop = Column(Float, nullable=True)

    # Establish cascade delete back-relationship
    trades = relationship("Trade", back_populates="position", cascade="all, delete-orphan", lazy="selectin")

class Trade(Base):
    """Audit log of order executions received from CCXT."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=True)
    exchange_order_id = Column(String, unique=True, index=True, nullable=False)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)  # BUY, SELL
    type = Column(String, nullable=False)  # MARKET, LIMIT
    price = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    strategy_name = Column(String, nullable=False, index=True)

    position = relationship("Position", back_populates="trades")

class DailyBalanceHistory(Base):
    """Daily audit snapshots of account balances and net asset equity."""
    __tablename__ = "daily_balance_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    daily_drawdown = Column(Float, default=0.0)

class StrategyState(Base):
    """Dynamic control flags and runtime parameters for active strategy instances."""
    __tablename__ = "strategy_state"

    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, unique=True, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    parameters = Column(JSON, nullable=True)  # Store dynamic indicators limits or overrides


class MarketCandle(Base):
    """Normalized OHLCV candle stream persisted from Binance market data."""
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_market_candle_symbol_tf_ts"),
    )

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    timeframe = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    closed = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
