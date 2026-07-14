"""
Groq Extraction Node

Uses the Groq LLM to extract structured sales/expense data from text.
Handles retry logic: if the first attempt returns invalid JSON,
retries once with a stricter prompt before giving up.
"""

import json
import re
import logging
from state import AgentState
from services.groq_client import groq_client

logger = logging.getLogger(__name__)


def _clean_json_response(raw: str) -> str:
    """
    Strip markdown code fences and extra whitespace from LLM response.

    LLMs sometimes wrap JSON in ```json ... ``` even when told not to.
    """
    # Remove markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    return cleaned.strip()


def groq_extract(state: AgentState) -> dict:
    """
    Extract structured data from text using Groq LLM.

    Uses state['extracted_text'] (from OCR) if available,
    otherwise falls back to state['telegram_message'].

    Implements one retry with a stricter prompt on parse failure.

    Returns:
        dict with 'parsed_json', 'retry_count', and optionally 'error'/'is_valid'.
    """
    # Determine the input text
    text = state.get("extracted_text", "") or state.get("telegram_message", "")
    retry_count = state.get("retry_count", 0)

    if not text:
        logger.warning("No text available for extraction")
        return {
            "parsed_json": {},
            "is_valid": False,
            "error": "No text provided for data extraction.",
        }

    logger.info(f"Extracting data from text ({len(text)} chars), attempt {retry_count + 1}")

    try:
        # First attempt or retry with stricter prompt
        if retry_count == 0:
            raw_response = groq_client.extract_data(text)
        else:
            raw_response = groq_client.extract_data_strict(text)

        # Clean and parse the response
        cleaned = _clean_json_response(raw_response)
        parsed = json.loads(cleaned)

        logger.info(f"Successfully parsed JSON: {json.dumps(parsed, indent=2)[:200]}")

        return {
            "parsed_json": parsed,
            "retry_count": retry_count,
        }

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed (attempt {retry_count + 1}): {e}")

        if retry_count < 1:
            # Retry once with stricter prompt
            logger.info("Retrying with stricter extraction prompt...")
            return {
                "retry_count": retry_count + 1,
                "parsed_json": {},
            }
        else:
            # Give up after retry
            logger.error("JSON extraction failed after retry")
            return {
                "parsed_json": {},
                "retry_count": retry_count,
                "is_valid": False,
                "error": (
                    "I couldn't understand the data format. "
                    "Please try again with a clearer format like:\n"
                    "Tea 150\nCoffee 90\nMilk 450 (expense)"
                ),
            }

    except Exception as e:
        logger.error(f"Groq extraction failed: {e}", exc_info=True)
        return {
            "parsed_json": {},
            "retry_count": retry_count,
            "is_valid": False,
            "error": f"Data extraction error: {str(e)}",
        }
