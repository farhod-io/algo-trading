"""Centralized Error Handling and Telegram Admin Alerting system.
"""

import logging
import time
import traceback
import asyncio
from typing import Dict, Optional
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID

# Per-context cooldown so a repeating failure (e.g. a scan loop erroring every
# 15 minutes) does not flood the admin chat. Errors are ALWAYS logged; only the
# Telegram dispatch is rate-limited.
ALERT_COOLDOWN_SECONDS = 300
_last_alert_sent: Dict[str, float] = {}


def _should_send_alert(context: str) -> bool:
    """True when this context has not produced an alert within the cooldown window."""
    now = time.monotonic()
    last = _last_alert_sent.get(context)
    if last is not None and (now - last) < ALERT_COOLDOWN_SECONDS:
        return False
    _last_alert_sent[context] = now
    return True


def reset_alert_cooldown(context: Optional[str] = None) -> None:
    """Testing/ops helper: clear the cooldown so the next alert goes out."""
    if context is None:
        _last_alert_sent.clear()
    else:
        _last_alert_sent.pop(context, None)


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

    if not _should_send_alert(context):
        logging.info(
            f"Admin alert for [{context}] suppressed (cooldown {ALERT_COOLDOWN_SECONDS}s). See log above."
        )
        return

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
