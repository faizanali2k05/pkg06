from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logger import logger
from src.database.repository import TradingRepository
from src.database.session import async_session
from src.exchange.binance_client import BinanceClient
from src.exchange.order_executor import OrderExecutor
from src.risk.exposure_control import check_exposure_limit
from src.risk.position_sizing import calculate_position_size
from src.risk.risk_manager import RiskManager
from src.risk.stop_loss import calculate_sl_tp, update_trailing_stop
from src.strategies.base_strategy import BaseStrategy


class StrategyManager:
    """Coordinates strategy plugins, signals, risk checks, and live position exits."""

    def __init__(self, order_executor: OrderExecutor, binance_client: BinanceClient) -> None:
        self.executor = order_executor
        self.client = binance_client
        self.strategies: dict[str, BaseStrategy] = {}

    def register_strategy(self, strategy: BaseStrategy) -> None:
        self.strategies[strategy.name] = strategy
        logger.info("Registered strategy '%s'.", strategy.name)

    def set_strategy_enabled(self, strategy_name: str, enabled: bool) -> bool:
        strategy = self.strategies.get(strategy_name)
        if not strategy:
            return False
        strategy.enabled = enabled
        logger.info("Strategy '%s' enabled=%s.", strategy_name, enabled)
        return True

    def update_strategy_parameters(self, strategy_name: str, parameters: dict[str, Any]) -> bool:
        strategy = self.strategies.get(strategy_name)
        if not strategy:
            return False
        strategy.update_parameters(parameters)
        return True

    async def sync_state_from_database(self, session: AsyncSession) -> None:
        for state in await TradingRepository.get_strategy_states(session):
            self.set_strategy_enabled(state.strategy_name, state.enabled)
            if state.parameters:
                self.update_strategy_parameters(state.strategy_name, state.parameters)

    async def warm_up_from_exchange(self) -> None:
        """Loads recent candles so long-window strategies can act immediately after startup."""
        for strategy in self.strategies.values():
            for symbol in strategy.symbols:
                try:
                    ohlcv = await self.client.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=settings.BINANCE_WS_TIMEFRAME,
                        limit=settings.WARMUP_CANDLES,
                    )
                    if not ohlcv:
                        continue
                    df = pd.DataFrame(
                        ohlcv,
                        columns=["timestamp", "open", "high", "low", "close", "volume"],
                    )
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    df.set_index("timestamp", inplace=True)
                    strategy.on_historical_candles(symbol, df)
                except Exception as exc:
                    logger.warning("Could not warm up %s for %s: %s", strategy.name, symbol, exc)

    async def handle_candle_update(self, symbol: str, tick: dict[str, Any]) -> None:
        await self._persist_closed_candle(symbol, tick)

        for name, strategy in self.strategies.items():
            if not strategy.enabled:
                continue

            try:
                signal = strategy.on_tick(symbol, tick)
                if signal:
                    asyncio.create_task(self._process_entry_signal(signal))
            except Exception as exc:
                logger.exception("Strategy '%s' failed to process tick on %s: %s", name, symbol, exc)

        async with async_session() as session:
            try:
                open_positions = await TradingRepository.get_open_positions(session)
                for position in open_positions:
                    if position.symbol == symbol:
                        await self._check_position_exit(session, position, tick)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.exception("Error during active position risk check: %s", exc)

    async def _persist_closed_candle(self, symbol: str, tick: dict[str, Any]) -> None:
        if not tick.get("closed"):
            return
        try:
            timestamp = datetime.utcfromtimestamp(int(tick["t"]) / 1000)
            async with async_session() as session:
                await TradingRepository.upsert_market_candle(
                    session=session,
                    symbol=symbol,
                    timeframe=str(tick.get("timeframe", settings.BINANCE_WS_TIMEFRAME)),
                    timestamp=timestamp,
                    open_price=float(tick["o"]),
                    high=float(tick["h"]),
                    low=float(tick["l"]),
                    close=float(tick["c"]),
                    volume=float(tick["v"]),
                    closed=True,
                )
                await session.commit()
        except Exception as exc:
            logger.warning("Failed to persist closed candle for %s: %s", symbol, exc)

    async def _process_entry_signal(self, signal: dict[str, Any]) -> None:
        if signal.get("action") != "BUY":
            return

        async with async_session() as session:
            try:
                symbol = signal["symbol"]
                strategy_name = signal["strategy_name"]
                price = float(signal["price"])
                atr = float(signal["atr"])
                params = signal["parameters"]

                open_positions = await TradingRepository.get_open_positions(session)
                if any(position.symbol == symbol and position.status == "OPEN" for position in open_positions):
                    logger.info("Entry ignored for %s because a position is already open.", symbol)
                    return

                balance_data = await self.client.get_balance()
                usdt_free = float(balance_data.get("USDT", {}).get("free", 0.0))
                current_equity = usdt_free + sum(
                    (position.qty * position.entry_price) + position.unrealized_pnl
                    for position in open_positions
                )

                stop_loss, take_profit = calculate_sl_tp(
                    price,
                    atr,
                    params["atr_multiplier"],
                    params["rr_ratio"],
                )
                qty = calculate_position_size(current_equity, price, stop_loss)
                if qty <= 0:
                    logger.warning("Sizing aborted: calculated quantity for %s is 0.", symbol)
                    return

                max_cash_qty = usdt_free / price if price > 0 else 0.0
                qty = min(qty, max_cash_qty)
                proposed_cost = qty * price
                if proposed_cost <= 0:
                    logger.warning("Entry rejected for %s due to insufficient free USDT.", symbol)
                    return

                try:
                    await RiskManager.validate_order(session, symbol, current_equity, proposed_cost)
                except Exception as exc:
                    logger.warning("Trade signal rejected by risk gate: %s", exc)
                    return

                if not check_exposure_limit(
                    open_positions=open_positions,
                    proposed_symbol=symbol,
                    proposed_cost=proposed_cost,
                    account_equity=current_equity,
                    max_single_asset_exposure=settings.MAX_SINGLE_ASSET_EXPOSURE,
                ):
                    return

                await self.executor.execute_entry(
                    db_session=session,
                    symbol=symbol,
                    strategy_name=strategy_name,
                    side="BUY",
                    qty=qty,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
                await session.commit()

            except Exception as exc:
                await session.rollback()
                logger.exception("Process entry signal failed: %s", exc)

    async def _check_position_exit(self, session: AsyncSession, position: Any, tick: dict[str, Any]) -> None:
        curr_price = float(tick["c"])
        curr_high = float(tick["h"])
        curr_low = float(tick["l"])

        unrealized_pnl = (curr_price - position.entry_price) * position.qty
        await TradingRepository.update_position_pnl(session, position.id, unrealized_pnl)

        if position.stop_loss is not None and curr_low <= position.stop_loss:
            logger.info("Stop loss hit for position %s (%s).", position.id, position.symbol)
            await self.executor.execute_exit(
                db_session=session,
                position_id=position.id,
                exit_price=position.stop_loss,
                reason="Stop Loss",
            )
            return

        if position.take_profit is not None and curr_high >= position.take_profit:
            logger.info("Take profit hit for position %s (%s).", position.id, position.symbol)
            await self.executor.execute_exit(
                db_session=session,
                position_id=position.id,
                exit_price=position.take_profit,
                reason="Take Profit",
            )
            return

        strategy = self.strategies.get(position.strategy_name)
        if not strategy or position.stop_loss is None:
            return

        atr_mult = strategy.parameters.get("atr_multiplier", 2.0)
        df = strategy.historical_data.get(position.symbol)
        if df is None or df.empty:
            return

        from src.indicators.atr import calculate_atr

        atr_series = calculate_atr(df["high"], df["low"], df["close"])
        if len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return

        new_stop = update_trailing_stop(curr_price, position.stop_loss, atr_series.iloc[-1], atr_mult)
        if new_stop > position.stop_loss:
            await TradingRepository.update_position_stop_loss(session, position.id, new_stop)
            logger.info("Position %s stop loss trailed to %.4f.", position.id, new_stop)
