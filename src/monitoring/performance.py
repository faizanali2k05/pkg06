from __future__ import annotations

from typing import Any


def summarize_closed_positions(positions: list[Any]) -> dict[str, Any]:
    total = len(positions)
    realized = [float(position.realized_pnl or 0.0) for position in positions]
    wins = [pnl for pnl in realized if pnl > 0]
    losses = [pnl for pnl in realized if pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "closed_positions": total,
        "net_realized_pnl": sum(realized),
        "win_rate": (len(wins) / total) if total else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss else None if gross_profit else 0.0,
        "average_realized_pnl": (sum(realized) / total) if total else 0.0,
        "largest_win": max(wins) if wins else 0.0,
        "largest_loss": min(losses) if losses else 0.0,
    }
