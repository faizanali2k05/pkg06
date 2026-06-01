from typing import Dict, Any
from src.core.logger import logger

def generate_text_report(results: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    """
    Constructs a clean, human-readable terminal performance report.
    
    Args:
        results: Simulation details from BacktestingEngine.run().
        metrics: Performance indices from calculate_backtest_metrics().
        
    Returns:
        str: Format-printed report.
    """
    lines = []
    lines.append("=" * 65)
    lines.append("                    APEXQUANT BACKTEST ANALYSIS")
    lines.append("=" * 65)
    lines.append(f" Initial Balance   : {results['initial_balance']:.2f} USDT")
    lines.append(f" Final Balance     : {results['final_balance']:.2f} USDT")
    lines.append(f" Net Profit        : {metrics['net_profit']:.2f} USDT ({metrics['total_return_pct']:.2f}%)")
    lines.append("-" * 65)
    lines.append(f" Total Executed    : {metrics['total_trades']} Trades")
    lines.append(f" Win Rate          : {metrics['win_rate'] * 100:.2f}%")
    lines.append(f" Profit Factor     : {metrics['profit_factor']:.2f}")
    lines.append(f" Max Drawdown      : {metrics['max_drawdown_pct'] * 100:.2f}%")
    lines.append(f" Sharpe Ratio      : {metrics['sharpe_ratio']:.2f}")
    lines.append(f" Avg PnL / Trade   : {metrics['avg_trade_pnl']:.2f} USDT")
    lines.append("=" * 65)

    trades = results.get("trades", [])
    if trades:
        lines.append("\nTrade Executions (Last 10 Trades):")
        header = f"{'Exit Date':<17} | {'Symbol':<8} | {'Qty':<8} | {'Entry':<8} | {'Exit':<8} | {'PnL (USDT)':<10} | {'Reason':<10}"
        lines.append(header)
        lines.append("-" * 65)
        for t in trades[-10:]:
            time_str = t["exit_time"].strftime("%m-%d %H:%M")
            lines.append(
                f"{time_str:<17} | {t['symbol']:<8} | {t['qty']:<8.4f} | {t['entry_price']:<8.2f} | "
                f"{t['exit_price']:<8.2f} | {t['net_pnl']:<10.2f} | {t['exit_reason']:<10}"
            )
        lines.append("=" * 65)
        
    return "\n".join(lines)
