"""
handlers.py — Telegram handlers with interactive mode selection.

/generate → inline keyboard → Mode 1 (text only) or Mode 2 (reference image)
/history  → last 5 generation records
"""

from __future__ import annotations

import asyncio
import datetime
import io
import logging
import os
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from . import db, figure_service, rate_limiter, s3

logger = logging.getLogger(__name__)

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Rate limit constants (for display in messages)
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "3"))
RATE_WINDOW = int(os.getenv("RATE_WINDOW_SECONDS", "60"))


# ConversationHandler states
MODE_SELECT, WAIT_TEXT, WAIT_PHOTO, WAIT_TEXT_AFTER_PHOTO = range(4)


def _save_output(png_bytes: bytes, prefix: str = "figure") -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{prefix}_{ts}.png"
    path.write_bytes(png_bytes)
    return path



async def _progress_loop(status_msg, chat, label: str, stop_event: asyncio.Event) -> None:
    """Edit the status message every 5 s to show elapsed time."""
    steps = ["⏳", "⌛"]
    elapsed = 0
    idx = 0
    while not stop_event.is_set():
        await asyncio.sleep(5)
        elapsed += 5
        if stop_event.is_set():
            break
        try:
            await status_msg.edit_text(
                f"{steps[idx % 2]} {label}\nElapsed: {elapsed}s..."
            )
            await chat.send_action(ChatAction.UPLOAD_PHOTO)
        except Exception:
            pass
        idx += 1


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to AutoFigure Bot!\n\n"
        "I generate professional academic figures from paper descriptions.\n\n"
        "Commands:\n"
        "/generate — Choose mode and generate a figure\n"
        "/history  — View your recent generations\n"
        "/help     — Usage guide"
    )


# ── /help ─────────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "How to use:\n\n"
        "1. Send /generate\n"
        "2. Choose a mode:\n"
        "   Mode 1 — Text only: paste your method description\n"
        "   Mode 2 — Reference image: send an image + description\n\n"
        "Generation takes 20-60 seconds.\n"
        "All outputs are saved locally."
    )


# ── /generate entry ───────────────────────────────────────────────────────────

async def generate_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("📝  Mode 1 — Text Only", callback_data="mode1")],
        [InlineKeyboardButton("🖼  Mode 2 — With Reference Image", callback_data="mode2")],
    ]
    await update.message.reply_text(
        "Choose generation mode:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return MODE_SELECT


async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "mode1":
        await query.edit_message_text(
            "Mode 1 selected — Text Only\n\n"
            "Please send your method description text now:"
        )
        return WAIT_TEXT
    else:
        await query.edit_message_text(
            "Mode 2 selected — Reference Image\n\n"
            "Step 1/2: Please send your reference image (no caption needed):"
        )
        return WAIT_PHOTO


# ── Mode 1: receive text ───────────────────────────────────────────────────────

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    method_text = update.message.text.strip()
    user_id = update.effective_user.id

    if rate_limiter.is_rate_limited(user_id):
        await update.message.reply_text(
            f"Too many requests. You can generate up to {RATE_LIMIT} figures per {RATE_WINDOW}s. Please wait."
        )
        return ConversationHandler.END

    status_msg = await update.message.reply_text("⏳ Generating figure...")

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(
        _progress_loop(status_msg, update.message.chat, "Generating figure...", stop_event)
    )

    try:
        png_bytes = await figure_service.generate_from_text(method_text, GEMINI_API_KEY)
        stop_event.set()
        await progress_task
        saved = _save_output(png_bytes, "figure")
        logger.info("Saved %s", saved)
        s3_url = s3.upload_figure(png_bytes, user_id)
        await status_msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(png_bytes),
            filename="figure.png",
            caption="Figure generated from paper text.",
        )
        db.log_request(user_id, method_text, "success", has_reference=False, s3_url=s3_url)
    except Exception as exc:
        stop_event.set()
        await progress_task
        logger.error("Text generation failed for user %s: %s", user_id, exc)
        await status_msg.edit_text(f"Generation failed: {str(exc)[:200]}")
        db.log_request(user_id, method_text, "failed", has_reference=False)

    return ConversationHandler.END


# ── Mode 2 Step 1: receive reference image ────────────────────────────────────

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the reference image, then ask for method text separately."""
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    context.user_data["ref_bytes"] = bytes(await photo_file.download_as_bytearray())

    await update.message.reply_text(
        "Image received!\n\n"
        "Step 2/2: Now send your method description text\n"
        "(no character limit — paste as much as you need):"
    )
    return WAIT_TEXT_AFTER_PHOTO


# ── Mode 2 Step 2: receive text, then generate ────────────────────────────────

async def receive_text_after_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    method_text = update.message.text.strip()
    user_id = update.effective_user.id
    ref_bytes: bytes = context.user_data.pop("ref_bytes", b"")

    if not ref_bytes:
        await update.message.reply_text("Reference image lost. Please start over with /generate.")
        return ConversationHandler.END

    if rate_limiter.is_rate_limited(user_id):
        await update.message.reply_text(
            f"Too many requests. You can generate up to {RATE_LIMIT} figures per {RATE_WINDOW}s. Please wait."
        )
        return ConversationHandler.END

    status_msg = await update.message.reply_text("⏳ Generating figure...")

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(
        _progress_loop(status_msg, update.message.chat, "Generating figure...", stop_event)
    )

    try:
        png_bytes = await figure_service.generate_with_reference(
            method_text, ref_bytes, GEMINI_API_KEY
        )
        stop_event.set()
        await progress_task
        saved = _save_output(png_bytes, "figure_ref")
        logger.info("Saved %s", saved)
        s3_url = s3.upload_figure(png_bytes, user_id)
        await status_msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(png_bytes),
            filename="figure.png",
            caption="Style-matched figure generated from paper text.",
        )
        db.log_request(user_id, method_text, "success", has_reference=True, s3_url=s3_url)
    except Exception as exc:
        stop_event.set()
        await progress_task
        logger.error("Style-matched generation failed for user %s: %s", user_id, exc)
        await status_msg.edit_text(f"Generation failed: {str(exc)[:200]}")
        db.log_request(user_id, method_text, "failed", has_reference=True)

    return ConversationHandler.END


# ── cancel ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ── /history ──────────────────────────────────────────────────────────────────

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    records = db.get_user_history(user_id)

    if not records:
        await update.message.reply_text(
            "No history found. Use /generate to create your first figure!"
        )
        return

    lines = ["Your recent generations:\n"]
    for i, item in enumerate(records, 1):
        ts = item.get("timestamp", "")[:19].replace("T", " ")
        preview = item.get("method_text", "")[:60]
        ref_icon = "[ref]" if item.get("has_reference") else "[txt]"
        ok_icon = "OK" if item.get("status") == "success" else "FAIL"
        lines.append(f"{i}. [{ok_icon}]{ref_icon} {ts}\n   {preview}...")

    await update.message.reply_text("\n".join(lines))


# ── ConversationHandler builder ───────────────────────────────────────────────

def build_generate_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("generate", generate_start)],
        states={
            MODE_SELECT:          [CallbackQueryHandler(mode_callback, pattern="^mode[12]$")],
            WAIT_TEXT:            [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
            WAIT_PHOTO:           [MessageHandler(filters.PHOTO, receive_photo)],
            WAIT_TEXT_AFTER_PHOTO:[MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text_after_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
