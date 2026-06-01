from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.core.config import settings
from src.core.logger import logger
from src.database.session import async_session, engine, init_db
from src.exchange.websocket_manager import BinanceWebSocketManager
from src.exchange.order_executor import OrderExecutor
from src.strategies.strategy_manager import StrategyManager
from src.strategies.ema_strategy import EMAStrategy
from src.strategies.breakout_strategy import BreakoutStrategy
from src.api.health import router as health_router
from src.api.routes import router as api_router, binance_client
from src.api.dashboard import router as dashboard_router
from src.database.repository import TradingRepository

websocket_manager = BinanceWebSocketManager()
order_executor = OrderExecutor(binance_client)
strategy_manager = StrategyManager(order_executor, binance_client)
scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)


async def record_daily_balance() -> None:
    """Persist account cash and estimated equity snapshots for drawdown controls."""
    try:
        async with async_session() as session:
            balance_data = await binance_client.get_balance()
            usdt_free = float(balance_data.get("USDT", {}).get("free", 0.0))

            open_positions = await TradingRepository.get_open_positions(session)
            total_open_value = sum((pos.qty * pos.entry_price) + pos.unrealized_pnl for pos in open_positions)
            total_equity = usdt_free + total_open_value

            latest = await TradingRepository.get_daily_balance_history(session, limit=1)
            day_start_equity = latest[0].equity if latest else total_equity
            daily_drawdown = (
                max(0.0, (day_start_equity - total_equity) / day_start_equity)
                if day_start_equity > 0
                else 0.0
            )

            await TradingRepository.create_daily_balance(session, usdt_free, total_equity, daily_drawdown)
            await session.commit()
            logger.info(
                "Daily balance audit completed. Cash: %.2f USDT, equity: %.2f USDT.",
                usdt_free,
                total_equity,
            )
    except Exception as exc:
        logger.exception("Daily balance audit failed: %s", exc)


async def bootstrap_strategies() -> None:
    symbols = settings.TRADING_SYMBOLS
    strategy_manager.register_strategy(EMAStrategy(symbols=symbols))
    strategy_manager.register_strategy(BreakoutStrategy(symbols=symbols))

    async with async_session() as session:
        await strategy_manager.sync_state_from_database(session)

    await strategy_manager.warm_up_from_exchange()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ApexQuant platform...")
    
    await init_db()
    
    async with async_session() as session:
        try:
            history = await TradingRepository.get_daily_balance_history(session, limit=1)
            if not history:
                balance_data = await binance_client.get_balance()
                usdt_free = balance_data.get("USDT", {}).get("free", 10000.0)
                await TradingRepository.create_daily_balance(session, usdt_free, usdt_free)
                await session.commit()
                logger.info(f"Initialized balance auditing history starting at {usdt_free:.2f} USDT")
        except Exception as init_err:
            logger.error(f"Failed to record starting balance audit: {init_err}")

    await binance_client.initialize()

    await bootstrap_strategies()

    websocket_manager.register_callback("kline", strategy_manager.handle_candle_update)
    if settings.ENABLE_WEBSOCKET_STREAMS:
        await websocket_manager.start()

    if not scheduler.running:
        scheduler.add_job(
            record_daily_balance,
            "interval",
            hours=24,
            id="daily_balance_audit",
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
        scheduler.start()

    logger.info("ApexQuant engine start complete. Running trading loops.")
    
    yield
    
    logger.info("Halting ApexQuant platform...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await websocket_manager.stop()
    await binance_client.close()
    await engine.dispose()
    logger.info("Clean shutdown completed. Bye!")

# Create FastAPI instance
app = FastAPI(
    title=settings.APP_NAME,
    description="ApexQuant production-grade algorithmic trading terminal",
    version="1.0.0",
    lifespan=lifespan
)
app.state.binance_client = binance_client
app.state.websocket_manager = websocket_manager
app.state.order_executor = order_executor
app.state.strategy_manager = strategy_manager

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.HTTP_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(dashboard_router)
app.include_router(health_router)
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
