"""
Receive Message Node

Parses an incoming Telegram update and populates the initial state
with the user's text message, chat ID, and photo information.

This node is the entry point of the LangGraph workflow.
"""

import logging
from state import AgentState
from services.branch_resolver import resolve_branch_in_message

logger = logging.getLogger(__name__)


def receive_message(state: AgentState) -> dict:
    """
    Process the initial Telegram message data already placed in state.

    The Telegram handler in app.py pre-populates:
      - telegram_message
      - chat_id
      - image_path (if photo)
      - has_image

    This node normalises and logs the received data.

    Returns:
        Updated state fields.
    """
    message = state.get("telegram_message", "")
    chat_id = state.get("chat_id", 0)
    has_image = state.get("has_image", False)
    image_path = state.get("image_path", "")

    logger.info(
        f"Received message from chat {chat_id}: "
        f"text='{message[:50]}...' has_image={has_image}"
    )

    # Resolve branch ID shortcuts (e.g. "b1: Tea 150" → branch="Main", text="Tea 150")
    cleaned_message = message.strip() if message else ""
    resolved_branch = ""
    if cleaned_message:
        cleaned_message, resolved_branch = resolve_branch_in_message(cleaned_message)
        if resolved_branch:
            logger.info(f"Branch resolved from ID shortcut: '{resolved_branch}'")

    # Ensure defaults for downstream nodes
    return {
        "telegram_message": cleaned_message,
        "chat_id": chat_id,
        "has_image": has_image,
        "image_path": image_path,
        "resolved_branch": resolved_branch,
        "retry_count": 0,
        "error": "",
        "validation_errors": [],
    }
