"""Entry point for the ICT‑ML‑Telegram signal system.

This script:
1. Loads configuration.
2. Starts the APScheduler background job that periodically scans the market.
3. Schedules automated weekly Sunday AI model retraining.
4. Launches the Telegram bot (polling mode).
"""

import warnings
warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from bot.telegram_bot import start_bot
from scheduler.scanner import scan_market, run_weekly_retraining
from config import SCAN_INTERVAL_MINUTES
from data.database import init_db
import services.notification_service  # Initializes the listener
import engine.paper_trading           # Initializes the paper trader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)


def main() -> None:
    init_db()
    scheduler = BackgroundScheduler()

    # 1. Market Scanner Job (runs every 15 minutes)
    scheduler.add_job(scan_market, "interval", minutes=SCAN_INTERVAL_MINUTES, max_instances=1)

    # 2. Automated Weekly Sunday AI Model Retraining Job (every Sunday at 00:00 UTC)
    scheduler.add_job(run_weekly_retraining, "cron", day_of_week="sun", hour=0, minute=0, max_instances=1)

    scheduler.start()
    logging.info("Market scanner started with interval %s minutes.", SCAN_INTERVAL_MINUTES)
    logging.info("Automated weekly AI retraining scheduled for every Sunday 00:00 UTC.")

    # Launch Telegram bot
    start_bot()


if __name__ == "__main__":
    main()
