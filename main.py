"""
OT Approval Bot - Main Entry Point
Local Polling Mode (for testing)
Optimized for performance
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path so all modules can use absolute imports
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    MessageHandler,
)

from config import TELEGRAM_BOT_TOKEN
from bot.handlers import (
    start_command,
    help_command,
    handle_callback,
    handle_new_request_input,
    handle_overday_input,
    handle_unknown_command,
    handle_idle_text,
)
from bot.states import ConversationState, get_conversation_context
from bot.guides import GUIDE_CONFIRM


# ========== LOGGING SETUP ==========
LOG_DIR = "logs"
LOG_FILE = "bot.log"


def setup_logging():
    """Setup file and console logging"""
    os.makedirs(LOG_DIR, exist_ok=True)

    daily_log = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

    logger = logging.getLogger("OTBot")
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear existing handlers

    file_handler = logging.FileHandler(daily_log, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%H:%M:%S'
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()


def log_event(event_type: str, details: str):
    """Log event with consistent format"""
    logger.info(f"{event_type} | {details}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages during conversation flows"""
    user_id = update.effective_user.id
    ctx = get_conversation_context(user_id)

    # Log incoming message (only if not idle)
    if update.message and ctx.state != ConversationState.IDLE:
        text = update.message.text[:30] if update.message.text else "None"
        log_event("MSG", f"U:{user_id} | State:{ctx.state.value} | {text}")

    # Only handle if in a conversation state that expects input
    conversation_input_states = [
        ConversationState.AWAITING_NAME,
        ConversationState.AWAITING_DEPARTMENT,
        ConversationState.AWAITING_OT_DATE,
        ConversationState.AWAITING_START_TIME,
        ConversationState.AWAITING_END_TIME,
        ConversationState.AWAITING_REASON,
        # Overday states
        ConversationState.AWAITING_OD_NAME,
        ConversationState.AWAITING_OD_DEPARTMENT,
        ConversationState.AWAITING_OD_START_DATE,
        ConversationState.AWAITING_OD_START_TIME,
        ConversationState.AWAITING_OD_END_TIME,
        ConversationState.AWAITING_OD_REASON,
    ]

    if ctx.state == ConversationState.IDLE:
        # Teks acak di luar pengajuan -> tunjukkan cara memakai bot
        await handle_idle_text(update, context)
        return

    if ctx.state in (ConversationState.CONFIRM_REQUEST,
                     ConversationState.CONFIRM_OVERDAY):
        # Sudah sampai tahap konfirmasi -> arahkan ke tombol
        await update.effective_message.reply_text(
            GUIDE_CONFIRM,
            parse_mode="Markdown",
        )
        return

    if ctx.state not in conversation_input_states:
        return

    if ctx.state in [
        ConversationState.AWAITING_OD_NAME,
        ConversationState.AWAITING_OD_DEPARTMENT,
        ConversationState.AWAITING_OD_START_DATE,
        ConversationState.AWAITING_OD_START_TIME,
        ConversationState.AWAITING_OD_END_TIME,
        ConversationState.AWAITING_OD_REASON,
    ]:
        await handle_overday_input(update, context)
    else:
        await handle_new_request_input(update, context)


async def main_async():
    """Main async function"""
    print("=" * 50)
    print("  OT APPROVAL BOT - STARTING")
    print("=" * 50)

    log_event("SYS", "Bot starting...")
    log_event("SYS", f"Log dir: {os.path.abspath(LOG_DIR)}")

    print(f"\nLogging to: {os.path.abspath(LOG_DIR)}/")
    print("\nBot akan membuat file log:")
    print("  - logs/bot_YYYYMMDD.log (log harian)")
    print("\n" + "=" * 50 + "\n")

    # Create bot instance
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    me = await bot.get_me()
    print(f"Bot: @{me.username}")

    # Build application with explicit bot
    app = Application.builder().bot(bot).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    # Perintah lain (typo / tidak dikenal) -> tampilkan daftar perintah yang benar
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Initialize and start polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    log_event("SYS", "Bot started! Polling active.")

    print("\n" + "=" * 50)
    print("  BOT STARTED SUCCESSFULLY!")
    print("  Polling mode active")
    print("  Tekan Ctrl+C untuk stop")
    print("=" * 50 + "\n")

    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        log_event("SYS", "Shutdown complete.")
        print("\n" + "=" * 50)
        print("  Bot stopped.")
        print("=" * 50)


def run_local():
    """Run bot in long polling mode (for local development)"""
    # Create new event loop for Python 3.10+
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        log_event("SYS", "Bot stopped by user")
        print("\n\n" + "=" * 50)
        print("  Bot shutting down...")
        print("  Bot stopped.")
        print("=" * 50)


if __name__ == "__main__":
    run_local()