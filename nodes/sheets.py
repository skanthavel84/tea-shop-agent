"""
Google Sheets Node

Writes validated sales and expense data to Google Sheets.
"""

import logging
from state import AgentState
from services.google_sheet import sheet_service

logger = logging.getLogger(__name__)


def write_sheets(state: AgentState) -> dict:
    """
    Write validated parsed_json data to Google Sheets.

    Reads sales, expenses, and branch from state['parsed_json'] and appends
    them to the respective worksheets.

    Returns:
        dict with 'sheet_status'.
    """
    parsed = state.get("parsed_json", {})
    record_date = parsed.get("date", "")
    branch = parsed.get("branch", "Main")

    if not parsed:
        logger.warning("No parsed data to write to sheets")
        return {"sheet_status": "error: no data"}

    try:
        sales = parsed.get("sales", [])
        expenses = parsed.get("expenses", [])
        total_rows = 0

        # Write sales
        if sales:
            rows_added = sheet_service.append_sales(sales, record_date, branch)
            total_rows += rows_added
            logger.info(f"Wrote {rows_added} sales rows for branch '{branch}'")

        # Write expenses
        if expenses:
            rows_added = sheet_service.append_expenses(expenses, record_date, branch)
            total_rows += rows_added
            logger.info(f"Wrote {rows_added} expense rows for branch '{branch}'")

        logger.info(f"Total rows written: {total_rows}")
        return {"sheet_status": "success"}

    except Exception as e:
        logger.error(f"Google Sheets write failed: {e}", exc_info=True)
        return {
            "sheet_status": f"error: {str(e)}",
            "error": f"Failed to save data to Google Sheets: {str(e)}",
        }
