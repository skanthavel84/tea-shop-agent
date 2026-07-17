"""
Branch Resolver Service

Resolves branch ID shortcuts in user messages.
Supports formats like:  b1:  B1:  #1:  branch 1:

If a branch ID is found at the start of the message, the service
returns the resolved branch name and the cleaned message text.
"""

import re
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

# Matches patterns at the start of a message:
#   b1:  B1:  #1:  branch 1:  Branch 1:
# Captures the numeric ID and the rest of the message.
BRANCH_ID_PATTERN = re.compile(
    r"^\s*(?:b|#|branch\s*)(\d+)\s*[:\-]\s*",
    re.IGNORECASE,
)


def resolve_branch_in_message(text: str) -> tuple:
    """
    Check if the message starts with a branch ID shortcut and resolve it.

    Args:
        text: The raw user message.

    Returns:
        (cleaned_text, resolved_branch_name)
        - cleaned_text: message with the branch ID prefix stripped
        - resolved_branch_name: the full branch name, or "" if no ID was found
    """
    if not text:
        return (text, "")

    match = BRANCH_ID_PATTERN.match(text)
    if not match:
        return (text, "")

    branch_id = match.group(1)  # e.g. "1", "2"
    branch_name = settings.BRANCH_MAP.get(branch_id, "")

    if not branch_name:
        logger.warning(
            f"Branch ID '{branch_id}' not found in BRANCH_MAP. "
            f"Available IDs: {list(settings.BRANCH_MAP.keys())}"
        )
        return (text, "")

    # Strip the matched prefix from the message
    cleaned_text = text[match.end():].strip()
    logger.info(f"Resolved branch ID '{branch_id}' → '{branch_name}'")

    return (cleaned_text, branch_name)


def get_branch_list_message() -> str:
    """
    Format the branch ID mapping as a readable Telegram message.

    Returns:
        Formatted string listing all branch IDs and names.
    """
    if not settings.BRANCH_MAP:
        return "⚠️ கிளைகள் அமைக்கப்படவில்லை. நிர்வாகியிடம் .env இல் BRANCH_MAP அமைக்க கேளுங்கள்."

    lines = [
        "🏪 *கிளை ID பட்டியல்*",
        "",
        "கிளை பெயரை முழுமையாக தட்டச்சு செய்வதற்கு பதிலாக இந்த குறுக்குவழிகளை பயன்படுத்துங்கள்:",
        "",
    ]

    for bid, bname in sorted(settings.BRANCH_MAP.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
        lines.append(f"  `b{bid}:` → {bname}")

    lines.append("")
    lines.append("*எடுத்துக்காட்டு:*  `b1: டீ 150, காபி 90`")
    lines.append("*இவையும் வேலை செய்யும்:*  `#1: டீ 150`  அல்லது  `B1: டீ 150`")

    return "\n".join(lines)
