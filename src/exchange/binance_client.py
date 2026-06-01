import ccxt.async_support as ccxt
import time
import uuid
from typing import List, Dict, Any, Optional
from src.core.config import settings
from src.core.logger import logger
from src.core.exceptions import ExchangeConnectionError, OrderExecutionError

class BinanceClient:
    """Wrapper for async interactions with Binance using CCXT, featuring an integrated dry-run simulator."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run or not settings.BINANCE_API_KEY
        self.exchange: Optional[ccxt.binance] = None

        if not self.dry_run:
            config = {
                "apiKey": settings.BINANCE_API_KEY,
                "secret": settings.BINANCE_SECRET_KEY,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot"
                }
            }
            if settings.BINANCE_USE_TESTNET:
                config["urls"] = {
                    "api": {
                        "public": "https://testnet.binance.vision/api",
                        "private": "https://testnet.binance.vision/api"
                    }
                }
            self.exchange = ccxt.binance(config)
            logger.info(f"Initialized live Binance Exchange Client (Testnet: {settings.BINANCE_USE_TESTNET})")
        else:
            logger.info("Initialized simulated Binance Client in DRY-RUN mode. Real funds are safe.")
            # Set up mock balance sheets with $10,000 USDT paper cash
            self.simulated_balance: Dict[str, Any] = {
                "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0},
                "BTC": {"free": 0.0, "used": 0.0, "total": 0.0},
                "ETH": {"free": 0.0, "used": 0.0, "total": 0.0},
                "SOL": {"free": 0.0, "used": 0.0, "total": 0.0}
            }

    async def initialize(self) -> None:
        """Loads live markets into CCXT cache."""
        if not self.dry_run and self.exchange:
            try:
                await self.exchange.load_markets()
            except Exception as e:
                raise ExchangeConnectionError(f"Failed to load market specs from Binance: {e}")

    async def close(self) -> None:
        """Gracefully tears down CCXT async connection pools."""
        if self.exchange:
            await self.exchange.close()

    async def get_balance(self) -> Dict[str, Any]:
        """Fetches asset balances across free, used, and total accounts."""
        if self.dry_run:
            # Reformat to match standard CCXT outputs
            return self._format_mock_balance()
        try:
            return await self.exchange.fetch_balance()
        except Exception as e:
            raise ExchangeConnectionError(f"Failed to fetch account balances from exchange: {e}")

    def _format_mock_balance(self) -> Dict[str, Any]:
        res = {"free": {}, "used": {}, "total": {}}
        for coin, details in self.simulated_balance.items():
            res["free"][coin] = details["free"]
            res["used"][coin] = details["used"]
            res["total"][coin] = details["total"]
            res[coin] = details
        return res

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200) -> List[List[Any]]:
        """Fetches historical market price candles (OHLCV)."""
        client = self.exchange
        temp_client = None
        if not client:
            temp_client = ccxt.binance({"enableRateLimit": True})
            client = temp_client
            
        try:
            if temp_client:
                await temp_client.load_markets()
            
            # Reformat symbol if ccxt demands it (e.g. BTC/USDT)
            ohlcv = await client.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            raise ExchangeConnectionError(f"Failed to fetch candlesticks for {symbol}: {e}")
        finally:
            if temp_client:
                await temp_client.close()

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Submits market or limit orders.
        In dry_run, local variables and order sheets are updated deterministically.
        """
        if self.dry_run:
            return self._simulate_order_execution(symbol, side, order_type, qty, price)

        if not self.exchange:
            raise OrderExecutionError("Live exchange client is not instantiated.")

        try:
            if order_type.upper() == "LIMIT" and price is None:
                raise OrderExecutionError("Limit order requires explicit price.")
            
            order = await self.exchange.create_order(
                symbol=symbol,
                type=order_type.lower(),
                side=side.lower(),
                amount=qty,
                price=price
            )
            return order
        except Exception as e:
            raise OrderExecutionError(f"Exchange rejected order submission: {e}")

    def _simulate_order_execution(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        # Perform dry run balance and price allocations
        base, quote = symbol.split("/")
        mock_price = price or 99999.0  # Fallback price
        cost = qty * mock_price

        # Safeguard simulated balance lookups
        if quote not in self.simulated_balance:
            self.simulated_balance[quote] = {"free": 0.0, "used": 0.0, "total": 0.0}
        if base not in self.simulated_balance:
            self.simulated_balance[base] = {"free": 0.0, "used": 0.0, "total": 0.0}

        side_upper = side.upper()
        if side_upper == "BUY":
            quote_free = self.simulated_balance[quote]["free"]
            if quote_free < cost:
                raise OrderExecutionError(
                    f"Dry Run balance insufficient. Need {cost:.4f} {quote}, but only have {quote_free:.4f} {quote}"
                )
            # Execute allocation updates
            self.simulated_balance[quote]["free"] -= cost
            self.simulated_balance[quote]["total"] -= cost
            self.simulated_balance[base]["free"] += qty
            self.simulated_balance[base]["total"] += qty
        elif side_upper == "SELL":
            base_free = self.simulated_balance[base]["free"]
            if base_free < qty:
                raise OrderExecutionError(
                    f"Dry Run balance insufficient. Need {qty:.4f} {base}, but only have {base_free:.4f} {base}"
                )
            # Execute allocation updates
            self.simulated_balance[base]["free"] -= qty
            self.simulated_balance[base]["total"] -= qty
            self.simulated_balance[quote]["free"] += cost
            self.simulated_balance[quote]["total"] += cost

        # Return mockup structure mirroring CCXT API payload
        return {
            "id": f"dry_order_{uuid.uuid4().hex[:12]}",
            "symbol": symbol,
            "type": order_type.lower(),
            "side": side.lower(),
            "price": mock_price,
            "amount": qty,
            "cost": cost,
            "status": "closed",
            "timestamp": int(time.time() * 1000),
            "fee": {"cost": cost * 0.001, "currency": quote}  # Standard 0.1% taker fee representation
        }
