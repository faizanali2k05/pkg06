from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtesting.engine import BacktestingEngine
from src.backtesting.metrics import calculate_backtest_metrics
from src.backtesting.reports import generate_text_report
from src.core.config import settings
from src.core.logger import logger
from src.database.repository import TradingRepository
from src.database.session import get_db_session
from src.exchange.binance_client import BinanceClient
from src.monitoring.performance import summarize_closed_positions
from src.strategies.breakout_strategy import BreakoutStrategy
from src.strategies.ema_strategy import EMAStrategy
from src.strategies.strategy_manager import StrategyManager

router = APIRouter(prefix="/api", tags=["Trading Operations"])

binance_client = BinanceClient()


class StrategyToggleRequest(BaseModel):
    strategy_name: str = Field(min_length=1)
    enabled: bool


class StrategyParamsRequest(BaseModel):
    strategy_name: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    symbol: str = Field(default="BTC/USDT", pattern=r"^[A-Z0-9]+/[A-Z0-9]+$")
    timeframe: Literal["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"] = "5m"
    limit: int = Field(default=500, ge=50, le=2000)
    strategy_name: Literal["EMA_Trend_Pullback", "Channel_Breakout"] = "EMA_Trend_Pullback"


def _runtime_manager(request: Request) -> StrategyManager | None:
    manager = getattr(request.app.state, "strategy_manager", None)
    return manager if isinstance(manager, StrategyManager) else None


@router.get("/positions")
async def get_active_positions(db: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    positions = await TradingRepository.get_open_positions(db)
    return [
        {
            "id": pos.id,
            "symbol": pos.symbol,
            "strategy_name": pos.strategy_name,
            "qty": pos.qty,
            "entry_price": pos.entry_price,
            "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
            "unrealized_pnl": pos.unrealized_pnl,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
            "trailing_stop": pos.trailing_stop,
        }
        for pos in positions
    ]


@router.get("/trades")
async def get_trade_history(
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    trades = await TradingRepository.get_trade_history(db, symbol=symbol, limit=limit)
    return [
        {
            "id": trade.id,
            "position_id": trade.position_id,
            "exchange_order_id": trade.exchange_order_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "type": trade.type,
            "price": trade.price,
            "qty": trade.qty,
            "commission": trade.commission,
            "timestamp": trade.timestamp.isoformat() if trade.timestamp else None,
            "strategy_name": trade.strategy_name,
        }
        for trade in trades
    ]


@router.get("/balance")
async def get_balances() -> dict[str, Any]:
    try:
        balance = await binance_client.get_balance()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to query account balances: {exc}") from exc

    filtered: dict[str, Any] = {"free": {}, "total": {}, "dry_run": binance_client.dry_run}
    for coin, value in balance.items():
        if coin in {"free", "used", "total"}:
            continue
        if isinstance(value, dict) and float(value.get("total", 0.0)) > 0.00001:
            filtered["free"][coin] = float(value.get("free", 0.0))
            filtered["total"][coin] = float(value.get("total", 0.0))
    return filtered


@router.get("/risk")
async def get_risk_summary(db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    positions = await TradingRepository.get_open_positions(db)
    balance = await binance_client.get_balance()
    usdt_free = float(balance.get("USDT", {}).get("free", 0.0))
    current_equity = usdt_free + sum((pos.qty * pos.entry_price) + pos.unrealized_pnl for pos in positions)
    history = await TradingRepository.get_daily_balance_history(db, limit=1)
    day_start_equity = history[0].equity if history else current_equity
    drawdown = ((day_start_equity - current_equity) / day_start_equity) if day_start_equity > 0 else 0.0

    exposure: dict[str, float] = {}
    for pos in positions:
        exposure[pos.symbol] = exposure.get(pos.symbol, 0.0) + (pos.qty * pos.entry_price)

    return {
        "current_equity": current_equity,
        "free_usdt": usdt_free,
        "open_positions": len(positions),
        "max_open_positions": settings.MAX_OPEN_POSITIONS,
        "risk_percent_per_trade": settings.RISK_PERCENT_PER_TRADE,
        "daily_drawdown_pct": max(0.0, drawdown),
        "daily_drawdown_limit_pct": settings.DAILY_DRAWDOWN_LIMIT_PCT,
        "trading_halted": drawdown >= settings.DAILY_DRAWDOWN_LIMIT_PCT,
        "exposure_by_symbol": exposure,
    }


@router.get("/performance")
async def get_performance_summary(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    closed_positions = await TradingRepository.get_closed_positions(db, limit=limit)
    return summarize_closed_positions(closed_positions)


@router.get("/strategies")
async def get_strategies(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    persisted_states = {
        state.strategy_name: state for state in await TradingRepository.get_strategy_states(db)
    }
    manager = _runtime_manager(request)
    runtime_strategies = manager.strategies if manager else {}

    names = sorted(set(persisted_states) | set(runtime_strategies))
    return [
        {
            "strategy_name": name,
            "enabled": runtime_strategies[name].enabled if name in runtime_strategies else persisted_states[name].enabled,
            "parameters": runtime_strategies[name].parameters if name in runtime_strategies else persisted_states[name].parameters,
            "runtime_loaded": name in runtime_strategies,
        }
        for name in names
    ]


@router.post("/strategy/toggle")
async def toggle_strategy(
    payload: StrategyToggleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        state = await TradingRepository.save_or_update_strategy_state(
            session=db,
            strategy_name=payload.strategy_name,
            enabled=payload.enabled,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update strategy: {exc}") from exc

    manager = _runtime_manager(request)
    runtime_updated = manager.set_strategy_enabled(payload.strategy_name, payload.enabled) if manager else False
    return {
        "strategy_name": state.strategy_name,
        "enabled": state.enabled,
        "runtime_updated": runtime_updated,
    }


@router.post("/strategy/update-params")
async def update_strategy_parameters(
    payload: StrategyParamsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        state = await TradingRepository.save_or_update_strategy_state(
            session=db,
            strategy_name=payload.strategy_name,
            enabled=True,
            parameters=payload.parameters,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to change parameters: {exc}") from exc

    manager = _runtime_manager(request)
    runtime_updated = manager.update_strategy_parameters(payload.strategy_name, payload.parameters) if manager else False
    return {
        "strategy_name": state.strategy_name,
        "parameters": state.parameters,
        "runtime_updated": runtime_updated,
    }


@router.get("/market/ticker")
async def get_market_ticker(symbol: str = Query(default="BTC/USDT")) -> dict[str, Any]:
    try:
        return await binance_client.fetch_ticker(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market/order-book")
async def get_market_order_book(
    symbol: str = Query(default="BTC/USDT"),
    limit: int = Query(default=20, ge=5, le=100),
) -> dict[str, Any]:
    try:
        return await binance_client.fetch_order_book(symbol, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market/candles")
async def get_stored_candles(
    symbol: str = Query(default="BTC/USDT"),
    timeframe: str = Query(default="1m"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    candles = await TradingRepository.get_latest_market_candles(db, symbol=symbol, timeframe=timeframe, limit=limit)
    return [
        {
            "symbol": candle.symbol,
            "timeframe": candle.timeframe,
            "timestamp": candle.timestamp.isoformat(),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "closed": candle.closed,
        }
        for candle in candles
    ]


@router.post("/backtest")
async def run_historical_backtest(payload: BacktestRequest) -> dict[str, Any]:
    try:
        logger.info("Triggering backtest for %s (%s, %s bars).", payload.symbol, payload.timeframe, payload.limit)
        ohlcv = await binance_client.fetch_ohlcv(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            limit=payload.limit,
        )
        if not ohlcv:
            raise HTTPException(status_code=404, detail="No historical candles returned from Binance API.")

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        strategy = (
            EMAStrategy(symbols=[payload.symbol])
            if payload.strategy_name == "EMA_Trend_Pullback"
            else BreakoutStrategy(symbols=[payload.symbol])
        )

        engine = BacktestingEngine(initial_balance=settings.BACKTEST_INITIAL_BALANCE)
        results = engine.run(symbol=payload.symbol, df=df, strategy=strategy)
        metrics = calculate_backtest_metrics(
            trades=results["trades"],
            equity_history=results["equity_history"],
            initial_balance=results["initial_balance"],
        )
        text_report = generate_text_report(results, metrics)

        serialized_trades = []
        for trade in results["trades"]:
            serialized_trade = trade.copy()
            serialized_trade["entry_time"] = trade["entry_time"].isoformat()
            serialized_trade["exit_time"] = trade["exit_time"].isoformat()
            serialized_trades.append(serialized_trade)

        return {
            "symbol": payload.symbol,
            "strategy": payload.strategy_name,
            "metrics": metrics,
            "trades_count": len(serialized_trades),
            "trades": serialized_trades,
            "text_report": text_report,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error executing historical backtest route.")
        raise HTTPException(status_code=500, detail=f"Failed to execute backtest: {exc}") from exc
