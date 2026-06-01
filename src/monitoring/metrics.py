from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeMetrics:
    equity: float
    open_positions: int
    daily_drawdown_pct: float
    trading_halted: bool


def calculate_daily_drawdown(day_start_equity: float, current_equity: float) -> float:
    if day_start_equity <= 0:
        return 0.0
    return max(0.0, (day_start_equity - current_equity) / day_start_equity)
