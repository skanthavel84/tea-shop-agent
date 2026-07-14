"""
Telegram API helper utilities.

Provides functions for downloading photos from Telegram messages
and other Telegram-specific operations.
"""

import os
import logging
from telegram import Update
from config.settings import settings

logger = logging.getLogger(__name__)


async def download_photo(update: Update) -> str:
    """
    Download the highest-resolution photo from a Telegram message.

    Args:
        update: The Telegram Update object containing the photo message.

    Returns:
        Local file path where the photo was saved.

    Raises:
        ValueError: If no photo is attached to the message.
    """
    if not update.message or not update.message.photo:
        raise ValueError("No photo found in the message")

    # Get the highest resolution photo (last in the list)
    photo = update.message.photo[-1]
    file_id = photo.file_id

    # Generate a unique filename
    filename = f"photo_{update.message.chat_id}_{update.message.message_id}.jpg"
    filepath = os.path.join(settings.TEMP_DIR, filename)

    # Download the file
    logger.info(f"Downloading photo {file_id} to {filepath}")
    telegram_file = await update.message.photo[-1].get_file()
    await telegram_file.download_to_drive(filepath)

    logger.info(f"Photo saved to {filepath}")
    return filepath


def cleanup_photo(filepath: str):
    """
    Remove a downloaded photo after processing.

    Args:
        filepath: Path to the photo file to delete.
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"Cleaned up photo: {filepath}")
    except OSError as e:
        logger.warning(f"Failed to clean up photo {filepath}: {e}")
