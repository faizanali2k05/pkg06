from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from src.core.logger import logger
from src.notifications.telegram import telegram_client


class AlertManager:
    """Formats platform events for Telegram or future notification transports."""

    @staticmethod
    def trigger_trade_alert(trade: Any, position: Any) -> None:
        AlertManager._dispatch(AlertManager._send_trade_alert(trade, position))

    @staticmethod
    async def _send_trade_alert(trade: Any, position: Any) -> None:
        is_entry = trade.side.upper() == "BUY"
        title = "ENTRY FILLED" if is_entry else "EXIT FILLED"

        msg = [
            f"<b>APEXQUANT - {title}</b>",
            f"<b>Symbol:</b> {trade.symbol}",
            f"<b>Strategy:</b> {trade.strategy_name}",
            f"<b>Execution Price:</b> {trade.price:.2f} USDT",
            f"<b>Amount:</b> {trade.qty:.5f}",
        ]

        if is_entry:
            msg.append(f"<b>Stop Loss:</b> {position.stop_loss:.2f} USDT")
            msg.append(f"<b>Take Profit:</b> {position.take_profit:.2f} USDT")
        else:
            pnl_pct = (trade.price - position.entry_price) / position.entry_price * 100
            pnl_sign = "+" if position.realized_pnl >= 0 else ""
            msg.append(
                f"<b>Realized PnL:</b> {pnl_sign}{position.realized_pnl:.2f} USDT "
                f"({pnl_sign}{pnl_pct:.2f}%)"
            )

        logger.info("Notification alert trigger: %s on %s", title, trade.symbol)
        await telegram_client.send_message("\n".join(msg))

    @staticmethod
    def trigger_risk_alert(event_message: str) -> None:
        AlertManager._dispatch(AlertManager._send_risk_alert(event_message))

    @staticmethod
    async def _send_risk_alert(event_message: str) -> None:
        msg = [
            "<b>APEXQUANT - RISK WARNING</b>",
            f"<b>Message:</b> {event_message}",
            "<i>Trading engine checks blocked new entries to protect capital.</i>",
        ]
        logger.critical("Risk alert trigger: %s", event_message)
        await telegram_client.send_message("\n".join(msg))

    @staticmethod
    def trigger_system_alert(event_message: str) -> None:
        AlertManager._dispatch(AlertManager._send_system_alert(event_message))

    @staticmethod
    async def _send_system_alert(event_message: str) -> None:
        msg = [
            "<b>APEXQUANT - SYSTEM ALERT</b>",
            f"<b>Message:</b> {event_message}",
        ]
        logger.warning("System alert trigger: %s", event_message)
        await telegram_client.send_message("\n".join(msg))

    @staticmethod
    def _dispatch(coro: Coroutine[Any, Any, Any]) -> None:
        try:
            asyncio.create_task(coro)
        except RuntimeError:
            logger.warning("No running event loop for alert dispatch; notification skipped.")
            coro.close()


alert_manager = AlertManager()
