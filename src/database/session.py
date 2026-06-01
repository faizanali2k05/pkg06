from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from src.core.config import settings
from src.core.logger import logger

# Define Base model for SQLAlchemy models to inherit
Base = declarative_base()

# Create async engine with robust pooling parameters
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,  # Check live connection before dispatching queries
    pool_size=10,
    max_overflow=20
)

# Create async session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db() -> None:
    """Initializes the database schema by creating all registered tables if they do not exist."""
    try:
        async with engine.begin() as conn:
            # We import models here to ensure they register on Base before metadata.create_all is called
            from src.database.models import Position, Trade, DailyBalanceHistory, StrategyState
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database tables: {e}")
        raise e

async def get_db_session() -> AsyncSession:
    """Dependency helper providing clean async database transaction flows."""
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Transaction failed and was rolled back: {e}")
            raise e
        finally:
            await session.close()
