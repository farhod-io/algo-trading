"""Centralized Error Handling and Telegram Admin Alerting system.
"""

import logging
import traceback
import asyncio
from typing import Optional
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID


async def send_admin_alert_async(message: str) -> None:
    """Send alert message to Telegram admin chat asynchronously."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        logging.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_ID missing. Admin alert skipped.")
        return

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_ADMIN_ID,
            text=f"🚨 **TIZIM XATOLIK OGOHLANTIRISHI** 🚨\n\n{message}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Failed to send Telegram admin alert: {e}")


def notify_admin_error(error: Exception, context: str = "") -> None:
    """Synchronous entry point to log and notify system admin of critical errors."""
    tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    log_msg = f"CRITICAL ERROR in [{context}]: {error}\n{tb_str}"
    logging.error(log_msg)

    alert_msg = f"**Kontekst:** `{context}`\n**Xatolik:** `{str(error)}`\n\n```python\n{tb_str[-500:]}\n```"

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.create_task(send_admin_alert_async(alert_msg))
        else:
            asyncio.run(send_admin_alert_async(alert_msg))
    except Exception as e:
        logging.error(f"Could not dispatch admin alert: {e}")
