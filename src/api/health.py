from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from typing import Dict, Any
from src.database.session import get_db_session
from src.core.config import settings
from src.core.logger import logger

router = APIRouter(prefix="/api/health", tags=["Health Checks"])

@router.get("")
async def get_health_status(db: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    """
    Detailed systems audit checking PostgreSQL connection pool, Redis, and Exchange wrappers.
    """
    health = {
        "status": "HEALTHY",
        "services": {
            "database": "UNKNOWN",
            "redis": "UNKNOWN",
            "exchange": "UNKNOWN"
        }
    }
    
    # 1. Database Check
    try:
        await db.execute(text("SELECT 1"))
        health["services"]["database"] = "CONNECTED"
    except Exception as db_err:
        logger.error(f"Health check failed: database connectivity issue: {db_err}")
        health["services"]["database"] = f"DISCONNECTED: {str(db_err)}"
        health["status"] = "UNHEALTHY"

    # 2. Redis Check
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2.0)
        await r.ping()
        await r.close()
        health["services"]["redis"] = "CONNECTED"
    except Exception as redis_err:
        logger.warning(f"Health check failed: Redis connectivity issue: {redis_err}")
        health["services"]["redis"] = f"DISCONNECTED: {str(redis_err)}"
        # Do not fail overall health if Redis is offline since it is secondary caching
        if health["status"] == "HEALTHY":
            health["status"] = "DEGRADED"

    # 3. Exchange Connection Check
    try:
        if settings.BINANCE_API_KEY:
            # Live/Testnet connectivity
            import ccxt.async_support as ccxt
            config = {
                "apiKey": settings.BINANCE_API_KEY,
                "secret": settings.BINANCE_SECRET_KEY,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"}
            }
            if settings.BINANCE_USE_TESTNET:
                config["urls"] = {
                    "api": {
                        "public": "https://testnet.binance.vision/api",
                        "private": "https://testnet.binance.vision/api"
                    }
                }
            exchange = ccxt.binance(config)
            await exchange.fetch_time()
            await exchange.close()
            health["services"]["exchange"] = "CONNECTED"
        else:
            health["services"]["exchange"] = "DRY_RUN (SIMULATION ACTIVE)"
    except Exception as ex_err:
        logger.error(f"Health check failed: Exchange connectivity issue: {ex_err}")
        health["services"]["exchange"] = f"DISCONNECTED: {str(ex_err)}"
        health["status"] = "UNHEALTHY"

    return health
