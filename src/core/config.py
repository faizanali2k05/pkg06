from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "ApexQuant"
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "logs"
    PORT: int = 8000
    HTTP_CORS_ORIGINS: list[str] = ["*"]
    
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET_KEY: str = ""
    BINANCE_USE_TESTNET: bool = True
    BINANCE_DRY_RUN: bool = True
    BINANCE_WS_BASE_URL: str = "wss://stream.binance.com:9443/stream"
    BINANCE_WS_TIMEFRAME: str = "1m"
    ENABLE_WEBSOCKET_STREAMS: bool = True
    ORDER_BOOK_DEPTH: int = Field(default=20, ge=5, le=20)
    
    ENCRYPTION_KEY: str = ""
    SECRET_KEY: str = "apexquant_super_secret_session_key_32_bytes_length!"
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/apexquant"
    
    REDIS_URL: str = "redis://localhost:6379/0"
    
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ENABLED: bool = False
    
    PAPER_STARTING_BALANCE: float = Field(default=10_000.0, gt=0)
    RISK_PERCENT_PER_TRADE: float = Field(default=0.01, gt=0, le=0.10)
    MAX_OPEN_POSITIONS: int = Field(default=3, ge=1)
    DAILY_DRAWDOWN_LIMIT_PCT: float = Field(default=0.03, gt=0, le=1)
    MAX_SINGLE_ASSET_EXPOSURE: float = Field(default=0.50, gt=0, le=1)
    COMMISSION_FEE: float = Field(default=0.001, ge=0, le=0.05)
    
    TRADING_SYMBOLS: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    WARMUP_CANDLES: int = Field(default=250, ge=50, le=1000)
    BACKTEST_INITIAL_BALANCE: float = Field(default=10_000.0, gt=0)
    SCHEDULER_TIMEZONE: str = "UTC"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("TRADING_SYMBOLS", "HTTP_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_csv_or_list(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str) and value and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

settings = Settings()
