import logging
import asyncio
from typing import Dict, Any
from abc import ABC, abstractmethod

from events.event_bus import event_bus
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class INotifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        pass


class TelegramNotifier(INotifier):
    def send(self, message: str) -> None:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logging.warning("Telegram credentials missing, skipping Telegram notification.")
            return

        async def _send_async():
            from telegram import Bot
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            async with bot:
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send_async())
        except RuntimeError:
            asyncio.run(_send_async())


class NotificationService:
    def __init__(self):
        self.notifiers = [
            TelegramNotifier()
        ]
        event_bus.subscribe("SIGNAL_GENERATED", self.handle_signal)

    def handle_signal(self, signal_data: Dict[str, Any]):
        pair = signal_data.get("pair", "BTCUSDT")
        direction = signal_data.get("direction", "UNKNOWN")
        confidence = signal_data.get("confidence", 0)
        timestamp = signal_data.get("timestamp", "Now")

        message = (
            f"🔔 YANGI SIGNAL ({pair}): {direction}\n"
            f"Ishonch: {confidence}%\n"
            f"Vaqt: {timestamp}\n"
            "Iltimos, hozirgi narxni yozib yuboring (Telegram botga)."
        )

        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception as e:
                logging.error(f"Failed to send notification via {type(notifier).__name__}: {e}")


# Global instance to auto-register subscribers
notification_service = NotificationService()
