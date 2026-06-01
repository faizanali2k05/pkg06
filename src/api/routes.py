from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
from src.database.session import get_db_session
from src.database.repository import TradingRepository
from src.exchange.binance_client import BinanceClient
from src.strategies.ema_strategy import EMAStrategy
from src.strategies.breakout_strategy import BreakoutStrategy
from src.backtesting.engine import BacktestingEngine
from src.backtesting.metrics import calculate_backtest_metrics
from src.backtesting.reports import generate_text_report
from src.core.logger import logger

router = APIRouter(prefix="/api", tags=["Trading Operations"])

# Shared binance client instance (we will inject it or load it dynamically)
# Injecting exchange client is easy:
binance_client = BinanceClient()

# --- PYDANTIC SCHEMAS ---
class StrategyToggleRequest(BaseModel):
    strategy_name: str
    enabled: bool

class StrategyParamsRequest(BaseModel):
    strategy_name: str
    parameters: Dict[str, Any]

class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    limit: int = 500
    strategy_name: str = "EMA_Trend_Pullback"

# --- POSITION & TRADE ENDPOINTS ---

@router.get("/positions")
async def get_active_positions(db: AsyncSession = Depends(get_db_session)) -> List[Dict[str, Any]]:
    """Returns all currently open positions."""
    positions = await TradingRepository.get_open_positions(db)
    return [
        {
            "id": pos.id,
            "symbol": pos.symbol,
            "strategy_name": pos.strategy_name,
            "qty": pos.qty,
            "entry_price": pos.entry_price,
            "entry_time": pos.entry_time.strftime("%Y-%m-%d %H:%M:%S") if pos.entry_time else "",
            "unrealized_pnl": pos.unrealized_pnl,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit
        } for pos in positions
    ]

@router.get("/trades")
async def get_trade_history(limit: int = 100, db: AsyncSession = Depends(get_db_session)) -> List[Dict[str, Any]]:
    """Returns execution trade logs."""
    trades = await TradingRepository.get_trade_history(db, limit=limit)
    return [
        {
            "id": t.id,
            "position_id": t.position_id,
            "exchange_order_id": t.exchange_order_id,
            "symbol": t.symbol,
            "side": t.side,
            "type": t.type,
            "price": t.price,
            "qty": t.qty,
            "commission": t.commission,
            "timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M:%S") if t.timestamp else "",
            "strategy_name": t.strategy_name
        } for t in trades
    ]

@router.get("/balance")
async def get_balances() -> Dict[str, Any]:
    """Fetches real-time asset allocations from active exchange client."""
    try:
        balance = await binance_client.get_balance()
        # Filter standard nonzero outputs for cleaner reading
        filtered = {"free": {}, "total": {}, "dry_run": binance_client.dry_run}
        for coin, val in balance.items():
            if coin in ["free", "used", "total"]:
                continue
            if isinstance(val, dict) and val.get("total", 0.0) > 0.00001:
                filtered["free"][coin] = val.get("free", 0.0)
                filtered["total"][coin] = val.get("total", 0.0)
        return filtered
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query account balances: {e}")

# --- STRATEGY CONTROL ENDPOINTS ---

@router.post("/strategy/toggle")
async def toggle_strategy(payload: StrategyToggleRequest, db: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    """Dynamically turns a strategy on or off."""
    try:
        state = await TradingRepository.save_or_update_strategy_state(
            session=db,
            strategy_name=payload.strategy_name,
            enabled=payload.enabled
        )
        await db.commit()
        return {
            "strategy_name": state.strategy_name,
            "enabled": state.enabled,
            "message": f"Strategy status successfully toggled to {state.enabled}."
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update strategy: {e}")

@router.post("/strategy/update-params")
async def update_strategy_parameters(payload: StrategyParamsRequest, db: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    """Adjusts specific configuration variables for a strategy."""
    try:
        state = await TradingRepository.save_or_update_strategy_state(
            session=db,
            strategy_name=payload.strategy_name,
            enabled=True,
            parameters=payload.parameters
        )
        await db.commit()
        return {
            "strategy_name": state.strategy_name,
            "parameters": state.parameters,
            "message": "Strategy parameters successfully updated."
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to change parameters: {e}")

# --- HISTORICAL BACKTEST ENDPOINT ---

@router.post("/backtest")
async def run_historical_backtest(payload: BacktestRequest) -> Dict[str, Any]:
    """
    Downloads historical candle data and simulates a backtest loop against the designated strategy.
    """
    try:
        logger.info(f"Triggering backtest endpoint for {payload.symbol} (Limit: {payload.limit})")
        # Download actual historical candles
        ohlcv = await binance_client.fetch_ohlcv(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            limit=payload.limit
        )
        
        if not ohlcv:
            raise HTTPException(status_code=404, detail="No historical candles returned from Binance API.")

        # Convert to Pandas DataFrame
        columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df = pd.DataFrame(ohlcv, columns=columns)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Initialize strategy instance
        symbols_list = [payload.symbol]
        if payload.strategy_name == "EMA_Trend_Pullback":
            strategy = EMAStrategy(symbols=symbols_list)
        elif payload.strategy_name == "Channel_Breakout":
            strategy = BreakoutStrategy(symbols=symbols_list)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown strategy name: {payload.strategy_name}")

        # Run Backtesting Engine
        engine = BacktestingEngine(initial_balance=10000.0)
        results = engine.run(symbol=payload.symbol, df=df, strategy=strategy)
        
        # Calculate metrics
        metrics = calculate_backtest_metrics(
            trades=results["trades"],
            equity_history=results["equity_history"],
            initial_balance=results["initial_balance"]
        )

        text_report = generate_text_report(results, metrics)
        
        # Reformat datetime objects in trades list for JSON serialization compatibility
        serialized_trades = []
        for t in results["trades"]:
            serialized_t = t.copy()
            serialized_t["entry_time"] = t["entry_time"].strftime("%Y-%m-%d %H:%M:%S")
            serialized_t["exit_time"] = t["exit_time"].strftime("%Y-%m-%d %H:%M:%S")
            serialized_trades.append(serialized_t)

        return {
            "symbol": payload.symbol,
            "strategy": payload.strategy_name,
            "metrics": metrics,
            "trades_count": len(serialized_trades),
            "trades": serialized_trades,
            "text_report": text_report
        }

    except Exception as e:
        logger.exception("Error executing historical backtest route.")
        raise HTTPException(status_code=500, detail=f"Failed to execute backtest: {str(e)}")
