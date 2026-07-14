"""
Tea Shop Accounting Bot — Entry Point

Starts the Telegram bot and connects incoming messages to the
LangGraph workflow for processing.

Usage:
    python app.py

Requires a .env file with the following variables:
    TELEGRAM_BOT_TOKEN
    GROQ_API_KEY
    GOOGLE_SHEETS_CREDENTIALS_FILE
    GOOGLE_SHEET_NAME
"""

import os
import sys
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configure logging before any other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import settings
from graph import workflow
from services.telegram_api import download_photo, cleanup_photo


# ── HTTP Health Check Server (Render Free Tier Workaround) ──────────

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP server handler for Render Free Tier health checks."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
        
    def log_message(self, format, *args):
        # Suppress logging HTTP requests to keep logs clean
        pass

def start_health_check_server():
    """Starts the health check server on the port supplied by Render."""
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Health check HTTP server listening on port {port}")
    server.serve_forever()


# ── Command Handlers ──────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — welcome message."""
    welcome = (
        "🍵 *Welcome to Tea Shop Accounting Bot!*\n\n"
        "I help you track daily sales and expenses across branches.\n\n"
        "*Quick Start:*\n"
        "• Send sales: `Tea 150, Coffee 90`\n"
        "• Send expenses: `Expense: Milk 450`\n"
        "• Specify branch: `Branch Main: Tea 150`\n"
        "• Send a photo of a receipt 📸\n"
        "• Ask for a report: `Today's report`\n\n"
        "_(If no branch specified, defaults to 'Main')_\n\n"
        "Type /help for more details."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command — usage instructions."""
    help_text = (
        "🍵 *Tea Shop Accounting Bot — Help*\n\n"
        "*Adding Sales:*\n"
        "Send items with amounts, one per line or comma-separated:\n"
        "  `Tea 150`\n"
        "  `Coffee 90, Samosa 30`\n\n"
        "*Adding Expenses:*\n"
        "Include words like 'expense', 'cost', 'purchase', or 'bought':\n"
        "  `Expense: Milk 450, Sugar 200`\n"
        "  `Bought Cups 500`\n\n"
        "*🏪 Specifying a Branch:*\n"
        "Include the branch name in your message:\n"
        "  `Branch Main: Tea 150, Coffee 90`\n"
        "  `Jayanagar branch: Expense Milk 450`\n"
        "  _(Defaults to 'Main' if not specified)_\n\n"
        "*Image Processing:*\n"
        "Send a photo of a receipt or handwritten note.\n"
        "I'll extract the data using OCR.\n\n"
        "*Reports:*\n"
        "  `Today's report` or `/report`\n"
        "  `Show summary`\n"
        "  Reports show per-branch breakdown with profit.\n\n"
        "*Commands:*\n"
        "/start — Welcome message\n"
        "/report — Today's summary (all branches)\n"
        "/help — This help message"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report command — shortcut for daily report."""
    await _run_workflow(update, text="Today's report", has_image=False)


# ── Message Handlers ─────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    text = update.message.text or ""
    logger.info(f"Text message from {update.effective_user.first_name}: '{text[:50]}'")
    await _run_workflow(update, text=text, has_image=False)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo messages."""
    caption = update.message.caption or ""
    logger.info(f"Photo message from {update.effective_user.first_name}, caption: '{caption[:50]}'")

    # Download the photo
    image_path = ""
    try:
        image_path = await download_photo(update)
    except Exception as e:
        logger.error(f"Failed to download photo: {e}")
        await update.message.reply_text(
            "❌ Failed to download the image. Please try again."
        )
        return

    await _run_workflow(update, text=caption, has_image=True, image_path=image_path)

    # Cleanup the downloaded photo
    if image_path:
        cleanup_photo(image_path)


# ── Workflow Runner ───────────────────────────────────────────────────

async def _run_workflow(
    update: Update,
    text: str,
    has_image: bool,
    image_path: str = "",
) -> None:
    """
    Execute the LangGraph workflow and send the result to the user.

    Args:
        update: Telegram Update object.
        text: The user's text message or caption.
        has_image: Whether the message includes a photo.
        image_path: Local path to the downloaded photo.
    """
    chat_id = update.effective_chat.id

    # Build initial state
    initial_state = {
        "telegram_message": text,
        "chat_id": chat_id,
        "has_image": has_image,
        "image_path": image_path,
        "extracted_text": "",
        "intent": "",
        "parsed_json": {},
        "validation_errors": [],
        "is_valid": None,
        "sheet_status": "",
        "report": "",
        "response": "",
        "error": "",
        "retry_count": 0,
        "ocr_confidence": 0.0,
    }

    # Send a "typing" indicator
    await update.effective_chat.send_action("typing")

    try:
        # Run the LangGraph workflow
        logger.info(f"Starting workflow for chat {chat_id}")
        result = workflow.invoke(initial_state)

        # Send the response
        response = result.get("response", "Something went wrong. Please try again.")
        logger.info(f"Workflow complete, sending response ({len(response)} chars)")

        # Split long messages (Telegram limit is 4096 chars)
        if len(response) <= 4096:
            await update.message.reply_text(response, parse_mode="Markdown")
        else:
            # Send in chunks
            for i in range(0, len(response), 4096):
                chunk = response[i : i + 4096]
                await update.message.reply_text(chunk, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again.\n"
            f"Error: {str(e)}"
        )


# ── Error Handler ─────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle uncaught errors from the Telegram bot."""
    logger.error(f"Telegram error: {context.error}", exc_info=context.error)


# ── Main ──────────────────────────────────────────────────────────────

def main():
    """Initialize and start the Telegram bot."""
    logger.info("=" * 50)
    logger.info("🍵 Tea Shop Accounting Bot Starting...")
    logger.info("=" * 50)

    # Build the Telegram application
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("report", cmd_report))

    # Register message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Register error handler
    app.add_error_handler(error_handler)

    # Start background health check server for Render Free Tier compatibility
    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()

    # Start polling
    logger.info("Bot is now polling for updates...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
