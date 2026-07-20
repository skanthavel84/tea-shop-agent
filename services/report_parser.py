"""
Report Parser — Extracts report type and date range from user messages.

Parses Tamil and English keywords to determine the report period:
  - daily (today): இன்றைய அறிக்கை, today's report
  - weekly: இந்த வாரம், this week, weekly report
  - monthly: இந்த மாதம், this month, monthly report
  - last_week: கடந்த வாரம், last week
  - custom: report from YYYY-MM-DD to YYYY-MM-DD
"""

import re
import logging
from datetime import date, timedelta
from typing import Tuple

logger = logging.getLogger(__name__)


# ── Keyword Patterns ─────────────────────────────────────────────────

WEEKLY_PATTERN = re.compile(
    r"\b(this\s*week|weekly|week\s*report|last\s*7\s*days)\b|"
    r"(இந்த\s*வாரம்|வாரம்\s*அறிக்கை|வார\s*அறிக்கை|7\s*நாள்)",
    re.IGNORECASE,
)

LAST_WEEK_PATTERN = re.compile(
    r"\b(last\s*week|previous\s*week|past\s*week)\b|"
    r"(கடந்த\s*வாரம்|முந்தைய\s*வாரம்)",
    re.IGNORECASE,
)

MONTHLY_PATTERN = re.compile(
    r"\b(this\s*month|monthly|month\s*report)\b|"
    r"(இந்த\s*மாதம்|மாத\s*அறிக்கை|மாதம்\s*அறிக்கை)",
    re.IGNORECASE,
)

LAST_MONTH_PATTERN = re.compile(
    r"\b(last\s*month|previous\s*month)\b|"
    r"(கடந்த\s*மாதம்|முந்தைய\s*மாதம்)",
    re.IGNORECASE,
)

CUSTOM_RANGE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s*(?:to|–|—|-|முதல்|வரை)\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def parse_report_request(text: str) -> Tuple[str, str, str]:
    """
    Parse the user's report request to determine report type and date range.

    Args:
        text: The user's message text.

    Returns:
        Tuple of (report_type, start_date, end_date) where dates are YYYY-MM-DD.
        report_type is one of: daily, weekly, last_week, monthly, last_month, custom
    """
    today = date.today()

    # ── Custom date range (check first — most specific) ───────────────
    custom_match = CUSTOM_RANGE_PATTERN.search(text)
    if custom_match:
        start = custom_match.group(1)
        end = custom_match.group(2)
        logger.info(f"Parsed custom date range: {start} to {end}")
        return "custom", start, end

    # ── Last month ────────────────────────────────────────────────────
    if LAST_MONTH_PATTERN.search(text):
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        start = first_of_prev_month.strftime("%Y-%m-%d")
        end = last_of_prev_month.strftime("%Y-%m-%d")
        logger.info(f"Parsed last month: {start} to {end}")
        return "last_month", start, end

    # ── Monthly (this month) ──────────────────────────────────────────
    if MONTHLY_PATTERN.search(text):
        start = today.replace(day=1).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        logger.info(f"Parsed this month: {start} to {end}")
        return "monthly", start, end

    # ── Last week ─────────────────────────────────────────────────────
    if LAST_WEEK_PATTERN.search(text):
        # Previous Monday to Sunday
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        start = last_monday.strftime("%Y-%m-%d")
        end = last_sunday.strftime("%Y-%m-%d")
        logger.info(f"Parsed last week: {start} to {end}")
        return "last_week", start, end

    # ── Weekly (this week) ────────────────────────────────────────────
    if WEEKLY_PATTERN.search(text):
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        start = monday.strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        logger.info(f"Parsed this week: {start} to {end}")
        return "weekly", start, end

    # ── Default: daily (today) ────────────────────────────────────────
    today_str = today.strftime("%Y-%m-%d")
    logger.info(f"Defaulting to daily report: {today_str}")
    return "daily", today_str, today_str
