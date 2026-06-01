import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Core app settings
    APP_NAME: str = "ApexQuant"
    ENV: str = "development"  # development, testing, production
    DEBUG: bool = True
    PORT: int = 8000
    
    # Exchange Connection
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET_KEY: str = ""
    BINANCE_USE_TESTNET: bool = True
    
    # Security Encryption Key (Should be a valid Fernet key or auto-generated fallback)
    ENCRYPTION_KEY: str = ""
    SECRET_KEY: str = "apexquant_super_secret_session_key_32_bytes_length!"
    
    # Database Settings (async pg connection string)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/apexquant"
    
    # Redis Cache Settings
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Telegram Notifications Settings
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ENABLED: bool = False
    
    # Risk Management Boundaries
    RISK_PERCENT_PER_TRADE: float = 0.01  # 1% Account Equity Risk per trade
    MAX_OPEN_POSITIONS: int = 3
    DAILY_DRAWDOWN_LIMIT_PCT: float = 0.03  # Stop trading if equity drops 3% daily
    
    # Default active symbols
    TRADING_SYMBOLS: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
