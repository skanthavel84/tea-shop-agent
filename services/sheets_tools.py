"""
CrewAI Tools — Google Sheets Access

Custom CrewAI tools that wrap the GoogleSheetService for agent use.
Each tool provides structured access to sales/expense data from Google Sheets.
"""

import json
import logging
from datetime import date
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from services.google_sheet import sheet_service

logger = logging.getLogger(__name__)


# ── Pydantic Input Schemas ────────────────────────────────────────────

class DailySummaryInput(BaseModel):
    """Input for fetching a single day's summary."""
    target_date: str = Field(
        default="",
        description="Date in YYYY-MM-DD format. Leave empty for today."
    )


class DateRangeInput(BaseModel):
    """Input for fetching data over a date range."""
    start_date: str = Field(
        description="Start date in YYYY-MM-DD format."
    )
    end_date: str = Field(
        description="End date in YYYY-MM-DD format."
    )


# ── CrewAI Tools ──────────────────────────────────────────────────────

class FetchDailySummaryTool(BaseTool):
    """Fetch a daily summary (sales, expenses, profit) from Google Sheets."""

    name: str = "fetch_daily_summary"
    description: str = (
        "Fetches the daily summary for a specific date from Google Sheets. "
        "Returns sales, expenses, and profit broken down by branch. "
        "Input: target_date in YYYY-MM-DD format, or empty string for today."
    )
    args_schema: Type[BaseModel] = DailySummaryInput

    def _run(self, target_date: str = "") -> str:
        """Execute the tool to fetch daily summary."""
        try:
            if not target_date:
                target_date = date.today().strftime("%Y-%m-%d")

            logger.info(f"FetchDailySummaryTool: Fetching summary for {target_date}")
            summary = sheet_service.get_daily_summary(target_date)
            return json.dumps(summary, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"FetchDailySummaryTool error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


class FetchDateRangeSalesTool(BaseTool):
    """Fetch all sales records for a date range from Google Sheets."""

    name: str = "fetch_date_range_sales"
    description: str = (
        "Fetches all sales records between start_date and end_date (inclusive) "
        "from Google Sheets. Returns a list of sales with date, branch, item, "
        "and amount. Input: start_date and end_date in YYYY-MM-DD format."
    )
    args_schema: Type[BaseModel] = DateRangeInput

    def _run(self, start_date: str, end_date: str) -> str:
        """Execute the tool to fetch sales for a date range."""
        try:
            logger.info(f"FetchDateRangeSalesTool: {start_date} to {end_date}")
            sales = sheet_service.get_sales_for_range(start_date, end_date)
            return json.dumps({
                "start_date": start_date,
                "end_date": end_date,
                "total_records": len(sales),
                "sales": sales,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"FetchDateRangeSalesTool error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


class FetchDateRangeExpensesTool(BaseTool):
    """Fetch all expense records for a date range from Google Sheets."""

    name: str = "fetch_date_range_expenses"
    description: str = (
        "Fetches all expense records between start_date and end_date (inclusive) "
        "from Google Sheets. Returns a list of expenses with date, branch, item, "
        "and amount. Input: start_date and end_date in YYYY-MM-DD format."
    )
    args_schema: Type[BaseModel] = DateRangeInput

    def _run(self, start_date: str, end_date: str) -> str:
        """Execute the tool to fetch expenses for a date range."""
        try:
            logger.info(f"FetchDateRangeExpensesTool: {start_date} to {end_date}")
            expenses = sheet_service.get_expenses_for_range(start_date, end_date)
            return json.dumps({
                "start_date": start_date,
                "end_date": end_date,
                "total_records": len(expenses),
                "expenses": expenses,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"FetchDateRangeExpensesTool error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


class FetchRangeSummaryTool(BaseTool):
    """Fetch aggregated summary for a date range with branch-wise and daily breakdowns."""

    name: str = "fetch_range_summary"
    description: str = (
        "Fetches an aggregated summary for a date range from Google Sheets. "
        "Returns branch-wise totals, daily totals, and grand totals for sales, "
        "expenses, and profit. Input: start_date and end_date in YYYY-MM-DD format."
    )
    args_schema: Type[BaseModel] = DateRangeInput

    def _run(self, start_date: str, end_date: str) -> str:
        """Execute the tool to fetch range summary."""
        try:
            logger.info(f"FetchRangeSummaryTool: {start_date} to {end_date}")
            summary = sheet_service.get_range_summary(start_date, end_date)
            return json.dumps(summary, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"FetchRangeSummaryTool error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
