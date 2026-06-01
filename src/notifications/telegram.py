from __future__ import annotations

import httpx
from src.core.config import settings
from src.core.logger import logger

class TelegramClient:
    """Asynchronous client interacting with the standard Telegram Bot API to dispatch live alerts."""

    def __init__(self) -> None:
        self.token: str = settings.TELEGRAM_BOT_TOKEN
        self.chat_id: str = settings.TELEGRAM_CHAT_ID
        self.enabled: bool = settings.TELEGRAM_ENABLED and bool(self.token) and bool(self.chat_id)
        
        if self.enabled:
            logger.info("Telegram notification client loaded and enabled.")
        else:
            logger.info("Telegram notification client is disabled or credentials are missing.")

    async def send_message(self, text: str) -> bool:
        """Sends an HTML formatted text alert message to the target chat channel."""
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            # Enforce strict timeouts to prevent exchange network loops from blocking
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.debug("Telegram alert dispatched successfully.")
                    return True
                else:
                    logger.error(f"Telegram API responded with error: {res.status_code} - {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Connection error: Failed to dispatch Telegram alert: {e}")
            return False

telegram_client = TelegramClient()
