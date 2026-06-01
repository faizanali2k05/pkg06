import asyncio
import pandas as pd
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.logger import logger
from src.database.repository import TradingRepository
from src.exchange.order_executor import OrderExecutor
from src.exchange.binance_client import BinanceClient
from src.risk.risk_manager import RiskManager
from src.risk.position_sizing import calculate_position_size
from src.risk.stop_loss import calculate_sl_tp, update_trailing_stop
from src.risk.exposure_control import check_exposure_limit
from src.database.session import async_session

class StrategyManager:
    """Registry and event coordinator directing market updates, signal processing, and position exits."""

    def __init__(self, order_executor: OrderExecutor, binance_client: BinanceClient) -> None:
        self.executor: OrderExecutor = order_executor
        self.client: BinanceClient = binance_client
        self.strategies: Dict[str, Any] = {}

    def register_strategy(self, strategy: Any) -> None:
        """Registers a strategy instance to receive real-time tick updates."""
        self.strategies[strategy.name] = strategy
        logger.info(f"Strategy registry updated: Registered '{strategy.name}' successfully.")

    async def handle_candle_update(self, symbol: str, tick: Dict[str, Any]) -> None:
        """
        Main entry point for WebSocket candlestick events.
        Routes tick to active strategies, checks exits for symbols, and executes orders.
        """
        # 1. Route tick to all registered strategies
        for name, strategy in self.strategies.items():
            if not strategy.enabled:
                continue

            try:
                signal = strategy.on_tick(symbol, tick)
                if signal:
                    # Spawn signal processing in a background task to prevent blocking the WebSocket stream thread
                    asyncio.create_task(self._process_entry_signal(signal))
            except Exception as strat_err:
                logger.error(f"Strategy '{name}' failed to process tick on {symbol}: {strat_err}")

        # 2. Check SL/TP and trailing stop conditions on open positions for this symbol
        async with async_session() as session:
            try:
                open_positions = await TradingRepository.get_open_positions(session)
                for pos in open_positions:
                    if pos.symbol == symbol:
                        await self._check_position_exit(session, pos, tick)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error during active positions risk check: {e}")

    async def _process_entry_signal(self, signal: Dict[str, Any]) -> None:
        """Takes a strategy BUY signal, runs risk audits, sizes position, and places entry order."""
        async with async_session() as session:
            try:
                symbol = signal["symbol"]
                strategy_name = signal["strategy_name"]
                price = signal["price"]
                atr = signal["atr"]
                params = signal["parameters"]

                # Fetch available cash balance to calculate sizing and check rules
                balance_data = await self.client.get_balance()
                usdt_free = balance_data.get("USDT", {}).get("free", 0.0)

                # Set initial risk boundaries using ATR
                sl, tp = calculate_sl_tp(price, atr, params["atr_multiplier"], params["rr_ratio"])

                # Size position quantity using 1% risk rule
                qty = calculate_position_size(usdt_free, price, sl)
                if qty <= 0:
                    logger.warning(f"Sizing aborted: Calculated quantity for {symbol} is 0.0")
                    return

                proposed_cost = qty * price

                # Check Master Risk Constraints (max positions, drawdown limits)
                try:
                    await RiskManager.validate_order(session, symbol, usdt_free, proposed_cost)
                except Exception as risk_err:
                    logger.warning(f"Trade signal rejected by Risk Gate: {risk_err}")
                    return

                # Check Concentration/Exposure Safeguards
                open_positions = await TradingRepository.get_open_positions(session)
                if not check_exposure_limit(open_positions, symbol, proposed_cost, usdt_free):
                    logger.warning("Trade signal rejected by Exposure Control.")
                    return

                # Authorized: Submit entry order to CCXT and save in DB
                await self.executor.execute_entry(
                    db_session=session,
                    symbol=symbol,
                    strategy_name=strategy_name,
                    side="BUY",
                    qty=qty,
                    price=price,
                    stop_loss=sl,
                    take_profit=tp
                )
                await session.commit()

            except Exception as e:
                await session.rollback()
                logger.error(f"Process entry signal failed: {e}")

    async def _check_position_exit(self, session: AsyncSession, position: Any, tick: Dict[str, Any]) -> None:
        """Evaluates active position prices against Stop-Loss and Take-Profit bounds."""
        curr_price = float(tick["c"])
        curr_high = float(tick["h"])
        curr_low = float(tick["l"])

        # 1. Evaluate Stop Loss hits
        if curr_low <= position.stop_loss:
            logger.info(
                f"STOP LOSS hit for position {position.id} ({position.symbol}). "
                f"Low ({curr_low:.2f}) <= SL price ({position.stop_loss:.2f}). Triggering exit."
            )
            await self.executor.execute_exit(
                db_session=session,
                position_id=position.id,
                exit_price=position.stop_loss,
                reason="Stop Loss"
            )
            return

        # 2. Evaluate Take Profit hits
        if curr_high >= position.take_profit:
            logger.info(
                f"TAKE PROFIT hit for position {position.id} ({position.symbol}). "
                f"High ({curr_high:.2f}) >= TP price ({position.take_profit:.2f}). Triggering exit."
            )
            await self.executor.execute_exit(
                db_session=session,
                position_id=position.id,
                exit_price=position.take_profit,
                reason="Take Profit"
            )
            return

        # 3. Dynamic Trailing Stop movement (if enabled by strategy params)
        strategy = self.strategies.get(position.strategy_name)
        if strategy:
            atr_mult = strategy.parameters.get("atr_multiplier", 2.0)
            df = strategy.historical_data.get(position.symbol)
            if df is not None and len(df) > 0:
                # Fetch trailing stop update value based on latest ATR calculation
                from src.indicators.atr import calculate_atr
                atr_series = calculate_atr(df["high"], df["low"], df["close"])
                if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                    curr_atr = atr_series.iloc[-1]
                    new_sl = update_trailing_stop(curr_price, position.stop_loss, curr_atr, atr_mult)
                    if new_sl > position.stop_loss:
                        await TradingRepository.update_position_stop_loss(session, position.id, new_sl)
                        logger.info(f"Position {position.id} Stop Loss adjusted to {new_sl:.4f} via trailing stop.")
