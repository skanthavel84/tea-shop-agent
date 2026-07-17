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
from functools import wraps
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
from services.branch_resolver import get_branch_list_message


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

# ── Authorization & Security ──────────────────────────────────────────

def is_authorized(user) -> bool:
    """Check if a Telegram User is authorized to use the bot."""
    if not settings.ALLOWED_USERS:
        # If no allowed users are configured, allow everyone (unrestricted mode)
        return True

    user_id = user.id
    username = user.username.lower() if user.username else ""

    # Check ID match or Username match
    if user_id in settings.ALLOWED_USERS:
        return True
    if username in settings.ALLOWED_USERS:
        return True

    return False


def authorized_only(func):
    """Decorator to restrict access to authorized users only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update or not update.effective_user:
            return
        
        user = update.effective_user
        if not is_authorized(user):
            user_id = user.id
            username_str = f" (@{user.username})" if user.username else ""
            logger.warning(
                f"Unauthorized access attempt by {user.first_name}{username_str} [ID: {user_id}]"
            )
            # Send a friendly denial message with the user's ID
            denial_msg = (
                "❌ *அணுகல் மறுக்கப்பட்டது.*\n\n"
                "இந்த பாட்டை பயன்படுத்த உங்களுக்கு அனுமதி இல்லை.\n"
                f"உங்கள் Telegram User ID: `{user_id}`\n\n"
                "நிர்வாகியிடம் `ALLOWED_USERS` பட்டியலில் சேர்க்க கேளுங்கள்."
            )
            if update.message:
                await update.message.reply_text(denial_msg, parse_mode="Markdown")
            return
            
        return await func(update, context, *args, **kwargs)
    return wrapper


# ── Command Handlers ──────────────────────────────────────────────────

@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — welcome message."""
    welcome = (
        "🍵 *டீ கடை கணக்கு பாட்க்கு வரவேற்கிறோம்!*\n\n"
        "கிளைகள் வழியாக தினசரி விற்பனை மற்றும் செலவுகளை கண்காணிக்க உதவுகிறேன்.\n\n"
        "*விரைவு தொடக்கம்:*\n"
        "• விற்பனை அனுப்புங்கள்: `டீ 150, காபி 90`\n"
        "• செலவுகள் அனுப்புங்கள்: `செலவு: பால் 450`\n"
        "• கிளை ID பயன்படுத்துங்கள்: `b1: டீ 150` அல்லது `#2: காபி 90`\n"
        "• ரசீது புகைப்படம் அனுப்புங்கள் 📸\n"
        "• அறிக்கை கேளுங்கள்: `இன்றைய அறிக்கை`\n\n"
        "_(கிளை ID பட்டியல் பார்க்க /branches அழுத்துங்கள்)_\n\n"
        "மேலும் விவரங்களுக்கு /help அழுத்துங்கள்."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command — usage instructions."""
    help_text = (
        "🍵 *டீ கடை கணக்கு பாட் — உதவி*\n\n"
        "*விற்பனை சேர்க்க:*\n"
        "பொருட்களை தொகையுடன் அனுப்புங்கள்:\n"
        "  `டீ 150`\n"
        "  `காபி 90, சமோசா 30`\n\n"
        "*செலவுகள் சேர்க்க:*\n"
        "'செலவு', 'வாங்கியது', 'பில்' போன்ற வார்த்தைகளை சேருங்கள்:\n"
        "  `செலவு: பால் 450, சர்க்கரை 200`\n"
        "  `வாங்கியது கப் 500`\n\n"
        "*🏪 கிளை குறிப்பிட:*\n"
        "கிளை ID குறுக்குவழிகளை பயன்படுத்துங்கள்:\n"
        "  `b1: டீ 150, காபி 90`\n"
        "  `#2: செலவு பால் 450`\n"
        "  `B3: காபி 90`\n"
        "  _(கிளை ID பட்டியல் பார்க்க /branches அழுத்துங்கள்)_\n"
        "  _(கிளை குறிப்பிடாவிட்டால் 'Main' ஆகும்)_\n\n"
        "*புகைப்பட செயலாக்கம்:*\n"
        "ரசீது அல்லது கையால் எழுதிய குறிப்பின் புகைப்படம் அனுப்புங்கள்.\n"
        "OCR மூலம் தரவை பிரித்தெடுப்பேன்.\n\n"
        "*அறிக்கைகள்:*\n"
        "  `இன்றைய அறிக்கை` அல்லது `/report`\n"
        "  `சுருக்கம் காட்டு`\n"
        "  அறிக்கைகள் கிளை வாரியான பிரிவு மற்றும் லாபத்தை காட்டும்.\n\n"
        "*கட்டளைகள்:*\n"
        "/start — வரவேற்பு செய்தி\n"
        "/branches — கிளை ID பட்டியல்\n"
        "/report — இன்றைய சுருக்கம் (அனைத்து கிளைகள்)\n"
        "/help — இந்த உதவி செய்தி"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


@authorized_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report command — shortcut for daily report."""
    await _run_workflow(update, text="Today's report", has_image=False)


@authorized_only
async def cmd_branches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /branches command — show branch ID mapping."""
    message = get_branch_list_message()
    await update.message.reply_text(message, parse_mode="Markdown")


# ── Message Handlers ─────────────────────────────────────────────────

@authorized_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    text = update.message.text or ""
    logger.info(f"Text message from {update.effective_user.first_name}: '{text[:50]}'")
    await _run_workflow(update, text=text, has_image=False)


@authorized_only
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
            "❌ படத்தை பதிவிறக்கம் செய்ய இயலவில்லை. மீண்டும் முயற்சிக்கவும்."
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

    # Format submitter name nicely
    user = update.effective_user
    if user:
        if user.username:
            user_info = f"{user.first_name} (@{user.username})"
        else:
            user_info = f"{user.first_name} ({user.id})"
    else:
        user_info = "Unknown"

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
        "user_info": user_info,
    }

    # Send a "typing" indicator
    await update.effective_chat.send_action("typing")

    try:
        # Run the LangGraph workflow
        logger.info(f"Starting workflow for chat {chat_id}")
        result = workflow.invoke(initial_state)

        # Send the response
        response = result.get("response", "ஏதோ தவறு நடந்தது. மீண்டும் முயற்சிக்கவும்.")
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
            "❌ எதிர்பாராத பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.\n"
            f"பிழை: {str(e)}"
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
    app.add_handler(CommandHandler("branches", cmd_branches))

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
