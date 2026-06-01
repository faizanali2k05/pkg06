import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.core.config import settings
from src.core.logger import logger
from src.database.session import init_db, engine
from src.exchange.binance_client import BinanceClient
from src.exchange.websocket_manager import BinanceWebSocketManager
from src.exchange.order_executor import OrderExecutor
from src.strategies.strategy_manager import StrategyManager
from src.strategies.ema_strategy import EMAStrategy
from src.strategies.breakout_strategy import BreakoutStrategy
from src.api.health import router as health_router
from src.api.routes import router as api_router, binance_client
from src.api.dashboard import router as dashboard_router
from src.database.repository import TradingRepository
from src.database.session import async_session

# Instantiate globally shared coordinators
websocket_manager = BinanceWebSocketManager()
order_executor = OrderExecutor(binance_client)
strategy_manager = StrategyManager(order_executor, binance_client)

async def log_daily_balance_loop() -> None:
    """Task loop to persist account balance and net equity valuations in SQL every 24 hours."""
    while True:
        try:
            # Repeat once a day
            await asyncio.sleep(24 * 60 * 60)
            async with async_session() as session:
                balance_data = await binance_client.get_balance()
                usdt_free = balance_data.get("USDT", {}).get("free", 0.0)
                
                open_positions = await TradingRepository.get_open_positions(session)
                total_open_cost = sum((pos.qty * pos.entry_price) + pos.unrealized_pnl for pos in open_positions)
                total_equity = usdt_free + total_open_cost
                
                await TradingRepository.create_daily_balance(session, usdt_free, total_equity)
                await session.commit()
                logger.info(f"Daily balance audit completed. Cash: {usdt_free:.2f} USDT, Equity: {total_equity:.2f} USDT")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Daily balance logger encountered error: {e}")
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP HANDLER ---
    logger.info("Initializing ApexQuant platform...")
    
    # 1. Build PostgreSQL schemas
    await init_db()
    
    # 2. Insert reference daily balance if database is brand new
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

    # 3. Warm up CCXT client markets
    await binance_client.initialize()

    # 4. Spin up Strategy Plugins
    symbols = settings.TRADING_SYMBOLS
    ema_strat = EMAStrategy(symbols=symbols)
    breakout_strat = BreakoutStrategy(symbols=symbols)
    
    strategy_manager.register_strategy(ema_strat)
    strategy_manager.register_strategy(breakout_strat)

    # 5. Connect WebSocket streams and hook up callbacks
    websocket_manager.register_callback("kline", strategy_manager.handle_candle_update)
    await websocket_manager.start()

    # 6. Launch background ledger worker
    daily_logger_task = asyncio.create_task(log_daily_balance_loop())

    logger.info("ApexQuant engine start complete. Running trading loops.")
    
    yield
    
    # --- SHUTDOWN HANDLER ---
    logger.info("Halting ApexQuant platform...")
    daily_logger_task.cancel()
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

# Apply CORS configs for API integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount Routes
app.include_router(dashboard_router)
app.include_router(health_router)
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
