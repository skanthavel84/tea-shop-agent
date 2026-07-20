"""
AgentState — the shared state that flows through the LangGraph workflow.

Each node reads from and writes to specific fields in this state.
LangGraph passes this state dict between nodes automatically.
"""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """
    Shared state for the Tea Shop Agent LangGraph workflow.

    Fields are grouped by the node that primarily writes to them.
    Using total=False so nodes only need to return the fields they update.
    """

    # ── Receive Message Node ──────────────────────────────────────────
    telegram_message: str       # Raw text content from the user
    chat_id: int                # Telegram chat ID for sending replies
    image_path: str             # Local path to downloaded photo (if any)
    has_image: bool             # Whether the message included a photo
    user_info: str              # Sender identity (username, first name, or ID)
    resolved_branch: str        # Branch name resolved from ID shortcut (e.g. b1: → "Main")


    # ── Detect Intent Node ────────────────────────────────────────────
    intent: str                 # ADD_SALES | ADD_EXPENSES | REPORT | HELP

    # ── OCR Node ──────────────────────────────────────────────────────
    extracted_text: str         # Text extracted from image via OCR
    ocr_confidence: float       # Average OCR confidence score (0.0–1.0)

    # ── Groq Extraction Node ─────────────────────────────────────────
    parsed_json: dict           # Structured extraction result from Groq
    retry_count: int            # Number of Groq extraction retries

    # ── Validation Node ───────────────────────────────────────────────
    validation_errors: list     # List of validation issue descriptions
    is_valid: bool              # Whether the extracted data passed validation

    # ── Sheets Node ───────────────────────────────────────────────────
    sheet_status: str           # "success" or error description

    # ── Report Node (Enhanced) ────────────────────────────────────────
    report: str                 # Formatted report text
    report_type: str            # daily | weekly | monthly | custom
    report_start_date: str      # Start date for range reports (YYYY-MM-DD)
    report_end_date: str        # End date for range reports (YYYY-MM-DD)

    # ── Reply Node ────────────────────────────────────────────────────
    response: str               # Final formatted message sent to user

    # ── Error Handling ────────────────────────────────────────────────
    error: str                  # Error message if something went wrong
