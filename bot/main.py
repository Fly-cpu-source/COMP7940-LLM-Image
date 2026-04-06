"""
main.py — Entry point for the AutoFigure Telegram Bot.

Run:
    python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

# Load .env from the COMP7940 directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Python 3.10+ no longer auto-creates an event loop — set one explicitly
asyncio.set_event_loop(asyncio.new_event_loop())

from telegram.ext import Application, CommandHandler

from .handlers import (
    build_generate_conversation,
    help_command,
    history_command,
    start,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# CloudWatch log handler (fails silently if credentials missing)
try:
    import watchtower
    _cw_client = boto3.client(
        "logs",
        region_name=os.getenv("AWS_REGION", "ap-southeast-1"),
    )
    _cw_handler = watchtower.CloudWatchLogHandler(
        log_group="/autofigure/bot",
        stream_name="bot-logs",
        boto3_client=_cw_client,
    )
    _cw_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(_cw_handler)
    logger.info("CloudWatch logging enabled.")
except Exception as _cw_exc:
    logger.warning("CloudWatch logging unavailable: %s", _cw_exc)


def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is not set")

    app = (
        Application.builder()
        .token(token)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(30)
        .pool_timeout(120)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(build_generate_conversation())

    logger.info("AutoFigure Bot starting...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
