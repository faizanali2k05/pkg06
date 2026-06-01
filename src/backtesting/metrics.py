import pandas as pd
import numpy as np
from typing import Dict, List, Any

def calculate_backtest_metrics(
    trades: List[Dict[str, Any]],
    equity_history: List[Dict[str, Any]],
    initial_balance: float
) -> Dict[str, Any]:
    """
    Computes performance analytical metrics based on simulated trade history and equity curves.
    
    Args:
        trades: Historical trades list from BacktestingEngine.
        equity_history: Chronological balance snapshots list.
        initial_balance: Starting allocation cash.
        
    Returns:
        Dict: Mathematical trading statistics.
    """
    if not trades or not equity_history:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "total_return_pct": 0.0,
            "net_profit": 0.0,
            "avg_trade_pnl": 0.0
        }

    df_trades = pd.DataFrame(trades)
    df_equity = pd.DataFrame(equity_history)

    # 1. Total and Winning trade counts
    total_trades = len(df_trades)
    winning_trades = len(df_trades[df_trades["net_pnl"] > 0])
    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    # 2. Gross profit factor accounting
    gross_profits = df_trades[df_trades["net_pnl"] > 0]["net_pnl"].sum()
    gross_losses = abs(df_trades[df_trades["net_pnl"] < 0]["net_pnl"].sum())
    
    if gross_losses == 0:
        profit_factor = None if gross_profits > 0 else 0.0
    else:
        profit_factor = float(gross_profits / gross_losses)

    # 3. Maximum Drawdown Calculation based on rolling peaks
    equity_series = df_equity["equity"]
    running_peaks = equity_series.cummax()
    drawdowns = (running_peaks - equity_series) / running_peaks
    max_dd = float(drawdowns.max())

    # 4. Annualized Sharpe Ratio calculation (Risk-Free assumed 0.0)
    # Re-sample equity checkpoints daily for uniform temporal spacing
    df_equity_daily = df_equity.set_index("timestamp").resample("D").last().ffill()
    daily_returns = df_equity_daily["equity"].pct_change().dropna()

    if len(daily_returns) > 1 and daily_returns.std() > 0:
        # Standard annualized multiplier for crypto (365 days)
        sharpe = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(365))
    else:
        sharpe = 0.0

    final_equity = equity_series.iloc[-1]
    net_profit = final_equity - initial_balance
    total_return = (net_profit / initial_balance) * 100
    avg_pnl = float(df_trades["net_pnl"].mean())

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe,
        "total_return_pct": total_return,
        "net_profit": net_profit,
        "avg_trade_pnl": avg_pnl
    }
