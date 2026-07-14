"""
Detect Intent Node

Classifies the user's message into one of the supported intents:
  - ADD_SALES: User is reporting sales data
  - ADD_EXPENSES: User is reporting expense data
  - REPORT: User wants to see a summary/report
  - HELP: User needs help or sent an unrelated message

Uses keyword matching first, falls back to Groq LLM for ambiguous cases.
"""

import re
import logging
from state import AgentState
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

# Keyword patterns for fast intent detection (avoids LLM call)
REPORT_KEYWORDS = re.compile(
    r"\b(report|summary|total|today'?s?\s*(sales|report|summary)|"
    r"how\s+much|kitna|aaj\s+ka)\b",
    re.IGNORECASE,
)

EXPENSE_KEYWORDS = re.compile(
    r"\b(expense|cost|purchase|bought|kharcha|kharid|bill)\b",
    re.IGNORECASE,
)

HELP_KEYWORDS = re.compile(
    r"\b(help|start|hi|hello|what\s+can\s+you|how\s+to\s+use)\b",
    re.IGNORECASE,
)


def detect_intent(state: AgentState) -> dict:
    """
    Determine the user's intent from their message.

    Strategy:
      1. Check for keyword matches (fast, no API call)
      2. If ambiguous, use Groq LLM for classification

    Returns:
        dict with 'intent' key.
    """
    text = state.get("telegram_message", "")

    if not text and state.get("has_image", False):
        # Image with no caption — assume sales data
        logger.info("Image without text, defaulting to ADD_SALES")
        return {"intent": "ADD_SALES"}

    if not text:
        return {"intent": "HELP"}

    # ── Fast keyword matching ─────────────────────────────────────────
    if REPORT_KEYWORDS.search(text):
        logger.info(f"Keyword match → REPORT: '{text[:40]}'")
        return {"intent": "REPORT"}

    if HELP_KEYWORDS.search(text) and len(text.split()) <= 5:
        logger.info(f"Keyword match → HELP: '{text[:40]}'")
        return {"intent": "HELP"}

    if EXPENSE_KEYWORDS.search(text):
        logger.info(f"Keyword match → ADD_EXPENSES: '{text[:40]}'")
        return {"intent": "ADD_EXPENSES"}

    # Check if the message looks like data (contains numbers → likely sales)
    has_numbers = bool(re.search(r"\d+", text))
    if has_numbers and len(text.split()) <= 20:
        logger.info(f"Number pattern match → ADD_SALES: '{text[:40]}'")
        return {"intent": "ADD_SALES"}

    # ── Fallback to LLM classification ────────────────────────────────
    logger.info(f"No keyword match, using Groq for intent: '{text[:40]}'")
    try:
        intent = groq_client.detect_intent(text)
        return {"intent": intent}
    except Exception as e:
        logger.error(f"Intent detection failed: {e}")
        return {"intent": "HELP"}
