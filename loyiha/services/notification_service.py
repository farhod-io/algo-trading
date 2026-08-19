import logging
import asyncio
from typing import Dict, Any, Set
from abc import ABC, abstractmethod

from events.event_bus import event_bus
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from bot.messages import format_signal_alert


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
            from telegram.error import RetryAfter, TimedOut, NetworkError, TelegramError
            
            try:
                bot = Bot(token=TELEGRAM_BOT_TOKEN)
                async with bot:
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
            except RetryAfter as e:
                logging.warning("Telegram Rate-limit hit (429). Retry-After: %s seconds.", e.retry_after)
            except TimedOut:
                logging.warning("Telegram request timed out. Message dropped safely without crashing.")
            except NetworkError as e:
                logging.warning("Telegram network connectivity error: %s", e)
            except TelegramError as e:
                logging.error("Telegram API Error: %s", e)
            except Exception as e:
                logging.error("Unexpected error sending Telegram message: %s", e)

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
        self._sent_idempotency_keys: Set[str] = set()
        event_bus.subscribe("SIGNAL_GENERATED", self.handle_signal)

    def is_duplicate_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Determines if this exact signal was already processed to prevent duplicate alerts."""
        pair = signal_data.get("pair", signal_data.get("symbol", "UNKNOWN"))
        direction = signal_data.get("direction", "UNKNOWN")
        timestamp = signal_data.get("timestamp", "")
        strategy = signal_data.get("source_strategy", signal_data.get("strategy", ""))
        entry = signal_data.get("entry_price", signal_data.get("entry", 0.0))

        key = f"{pair}_{direction}_{timestamp}_{strategy}_{entry}"
        if key in self._sent_idempotency_keys:
            return True

        self._sent_idempotency_keys.add(key)
        # Keep set bounded to prevent unbounded memory growth
        if len(self._sent_idempotency_keys) > 1000:
            self._sent_idempotency_keys.pop()
        return False

    def handle_signal(self, signal_data: Dict[str, Any]):
        if self.is_duplicate_signal(signal_data):
            logging.info("NotificationService: Duplicate signal suppressed (%s %s).", signal_data.get("pair"), signal_data.get("direction"))
            return

        message = format_signal_alert(signal_data)

        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception as e:
                logging.error(f"Failed to send notification via {type(notifier).__name__}: {e}")


# Global instance to auto-register subscribers
notification_service = NotificationService()
