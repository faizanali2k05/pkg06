import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from src.core.logger import logger
from src.risk.position_sizing import calculate_position_size
from src.risk.stop_loss import calculate_sl_tp, update_trailing_stop

class BacktestingEngine:
    """Event-driven historical trading simulation engine matching live WebSocket routing structures."""

    def __init__(self, initial_balance: float = 10000.0, commission_fee: float = 0.001) -> None:
        self.initial_balance: float = initial_balance
        self.balance: float = initial_balance
        self.commission_fee: float = commission_fee
        
        self.trades: List[Dict[str, Any]] = []
        self.equity_history: List[Dict[str, Any]] = []
        self.active_position: Optional[Dict[str, Any]] = None

    def run(self, symbol: str, df: pd.DataFrame, strategy: Any) -> Dict[str, Any]:
        """
        Runs event-driven backtesting by feeding sequential candles to the strategy.
        
        Args:
            symbol: Ticker symbol (e.g. BTC/USDT).
            df: Historical DataFrame with DatetimeIndex and columns [open, high, low, close, volume].
            strategy: A concrete strategy instance (e.g. EMAStrategy).
            
        Returns:
            Dict: Summary results including trade logs and equity progression.
        """
        logger.info(f"Starting historical simulation on {symbol} (Candles: {len(df)})")
        
        # Reset engine states
        self.balance = self.initial_balance
        self.trades = []
        self.equity_history = []
        self.active_position = None
        
        # Warmup strategy with initial slice
        warmup_size = min(250, len(df))
        strategy.on_historical_candles(symbol, df.iloc[:warmup_size])
        
        # Loop through simulation data
        for i in range(warmup_size, len(df)):
            row = df.iloc[i]
            timestamp = df.index[i]
            
            # Format raw series row to mock socket tick structure
            tick = {
                "t": int(timestamp.timestamp() * 1000),
                "o": float(row["open"]),
                "h": float(row["high"]),
                "l": float(row["low"]),
                "c": float(row["close"]),
                "v": float(row["volume"]),
                "closed": True
            }
            
            curr_price = tick["c"]
            curr_high = tick["h"]
            curr_low = tick["l"]
            
            # 1. Check exit events on active position before routing new ticks
            if self.active_position:
                pos = self.active_position
                
                # Check Stop Loss
                if curr_low <= pos["stop_loss"]:
                    self._close_position_mock(
                        exit_price=pos["stop_loss"],
                        timestamp=timestamp,
                        reason="Stop Loss"
                    )
                # Check Take Profit
                elif curr_high >= pos["take_profit"]:
                    self._close_position_mock(
                        exit_price=pos["take_profit"],
                        timestamp=timestamp,
                        reason="Take Profit"
                    )
                # Check Trailing Stop updates
                else:
                    # Update SL if price moves in our favor using newest ATR calculations
                    # Feed high, low, close up to current index
                    sub_df = df.iloc[:i+1]
                    from src.indicators.atr import calculate_atr
                    atr_series = calculate_atr(sub_df["high"], sub_df["low"], sub_df["close"])
                    if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                        curr_atr = atr_series.iloc[-1]
                        atr_mult = strategy.parameters.get("atr_multiplier", 2.0)
                        
                        new_sl = update_trailing_stop(curr_price, pos["stop_loss"], curr_atr, atr_mult)
                        if new_sl > pos["stop_loss"]:
                            self.active_position["stop_loss"] = new_sl

            # 2. Track equity snapshot (cash + unrealized PnL)
            unrealized_pnl = 0.0
            if self.active_position:
                pos = self.active_position
                unrealized_pnl = (curr_price - pos["entry_price"]) * pos["qty"]
                
            current_equity = self.balance + unrealized_pnl
            self.equity_history.append({
                "timestamp": timestamp,
                "balance": self.balance,
                "equity": current_equity,
                "drawdown": (self.initial_balance - current_equity) / self.initial_balance
            })
            
            # 3. Route tick to strategy and process any signals
            signal = strategy.on_tick(symbol, tick)
            if signal and not self.active_position:
                price = signal["price"]
                atr = signal["atr"]
                params = signal["parameters"]
                
                # Sizing: risk 1% of current equity
                sl, tp = calculate_sl_tp(price, atr, params["atr_multiplier"], params["rr_ratio"])
                qty = calculate_position_size(current_equity, price, sl, risk_pct=0.01)
                
                if qty > 0:
                    cost = qty * price
                    fee = cost * self.commission_fee
                    
                    if self.balance >= (cost + fee):
                        self.balance -= (cost + fee)
                        self.active_position = {
                            "symbol": symbol,
                            "qty": qty,
                            "entry_price": price,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "entry_time": timestamp,
                            "entry_fee": fee
                        }
                        logger.info(
                            f"[{timestamp}] Backtest Entry BUY {qty:.4f} {symbol} at {price:.2f} "
                            f"(Cost: {cost:.2f} USDT, SL: {sl:.2f}, TP: {tp:.2f})"
                        )

        # Force close any open positions at final candle to capture final equity metrics
        if self.active_position:
            final_row = df.iloc[-1]
            final_time = df.index[-1]
            self._close_position_mock(
                exit_price=float(final_row["close"]),
                timestamp=final_time,
                reason="End of Backtest"
            )

        logger.info(
            f"Backtest completed. Total trades: {len(self.trades)}, "
            f"Ending Equity: {self.balance:.2f} USDT (Return: {((self.balance - self.initial_balance) / self.initial_balance * 100):.2f}%)"
        )
        return {
            "trades": self.trades,
            "equity_history": self.equity_history,
            "initial_balance": self.initial_balance,
            "final_balance": self.balance
        }

    def _close_position_mock(self, exit_price: float, timestamp: pd.Timestamp, reason: str) -> None:
        if not self.active_position:
            return
            
        pos = self.active_position
        qty = pos["qty"]
        gross_value = qty * exit_price
        exit_fee = gross_value * self.commission_fee
        
        # Add values back to balance
        self.balance += (gross_value - exit_fee)
        
        # Calculate gross and net realized PnL
        gross_pnl = (exit_price - pos["entry_price"]) * qty
        net_pnl = gross_pnl - pos["entry_fee"] - exit_fee
        
        self.trades.append({
            "symbol": pos["symbol"],
            "qty": qty,
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "entry_time": pos["entry_time"],
            "exit_time": timestamp,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "entry_fee": pos["entry_fee"],
            "exit_fee": exit_fee,
            "exit_reason": reason,
            "return_pct": (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
        })
        
        logger.info(
            f"[{timestamp}] Backtest Exit {qty:.4f} {pos['symbol']} at {exit_price:.2f} "
            f"(PnL: {net_pnl:.2f} USDT, Reason: {reason})"
        )
        self.active_position = None
