import asyncio
from typing import Any
from src.core.logger import logger
from src.notifications.telegram import telegram_client

class AlertManager:
    """Formats and compiles platform events into clean notification templates."""

    @staticmethod
    def trigger_trade_alert(trade: Any, position: Any) -> None:
        """Formulates trade entry or exit reports and dispatches them asynchronously."""
        asyncio.create_task(AlertManager._send_trade_alert(trade, position))

    @staticmethod
    async def _send_trade_alert(trade: Any, position: Any) -> None:
        is_entry = trade.side.upper() == "BUY"
        emoji = "🟢" if is_entry else "🔴"
        title = "ENTRY FILLED" if is_entry else "EXIT FILLED"
        
        msg = [
            f"{emoji} <b>APEXQUANT - {title}</b>",
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
            msg.append(f"<b>Realized PnL:</b> {pnl_sign}{position.realized_pnl:.2f} USDT ({pnl_sign}{pnl_pct:.2f}%)")
            msg.append(f"<b>Exit Reason:</b> {trade.type} market sell")

        text_payload = "\n".join(msg)
        
        # Log to core console
        logger.info(f"Notification alert trigger: {title} on {trade.symbol}")
        # Send via Telegram bot channels
        await telegram_client.send_message(text_payload)

    @staticmethod
    def trigger_risk_alert(event_message: str) -> None:
        """Formulates risk warning reports and dispatches them asynchronously."""
        asyncio.create_task(AlertManager._send_risk_alert(event_message))

    @staticmethod
    async def _send_risk_alert(event_message: str) -> None:
        msg = [
            "⚠️ <b>APEXQUANT - RISK WARNING</b>",
            f"<b>Message:</b> {event_message}",
            "<i>Trading engine checks blocked new entries to protect capital.</i>"
        ]
        text_payload = "\n".join(msg)
        logger.critical(f"Risk Alert trigger: {event_message}")
        await telegram_client.send_message(text_payload)

alert_manager = AlertManager()
