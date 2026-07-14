"""
Validation Node

Validates the structured JSON extracted by the Groq node.
Checks for:
  - Valid JSON structure (date, sales, expenses arrays)
  - Non-empty item names
  - Positive numeric amounts
  - No duplicate items within the same category
  - Date format validity

Sets is_valid and populates validation_errors list.
"""

import logging
from datetime import datetime, date
from state import AgentState

logger = logging.getLogger(__name__)


def validate(state: AgentState) -> dict:
    """
    Validate the parsed JSON data from Groq extraction.

    Returns:
        dict with 'is_valid', 'validation_errors', and optionally updated 'parsed_json'.
    """
    parsed = state.get("parsed_json", {})
    errors = []

    # ── Check if we already have an error from extraction ─────────────
    if state.get("error"):
        return {
            "is_valid": False,
            "validation_errors": [state["error"]],
        }

    if not parsed:
        return {
            "is_valid": False,
            "validation_errors": ["No data was extracted. Please try again."],
        }

    # ── Validate date ─────────────────────────────────────────────────
    record_date = parsed.get("date", "")
    if not record_date:
        # Default to today
        record_date = date.today().strftime("%Y-%m-%d")
        parsed["date"] = record_date
        logger.info(f"No date provided, defaulting to today: {record_date}")
    else:
        try:
            datetime.strptime(record_date, "%Y-%m-%d")
        except ValueError:
            errors.append(
                f"Invalid date format: '{record_date}'. Expected YYYY-MM-DD."
            )

    # ── Validate branch ───────────────────────────────────────────────
    branch = parsed.get("branch", "")
    if not branch or not str(branch).strip():
        branch = "Main"
        parsed["branch"] = branch
        logger.info("No branch provided, defaulting to 'Main'")
    else:
        parsed["branch"] = str(branch).strip()
        logger.info(f"Branch: {parsed['branch']}")

    # ── Validate sales ────────────────────────────────────────────────
    sales = parsed.get("sales", [])
    if not isinstance(sales, list):
        errors.append("'sales' must be a list.")
        sales = []

    seen_sales = set()
    for i, item in enumerate(sales):
        item_errors = _validate_entry(item, "Sales", i + 1)
        errors.extend(item_errors)

        # Check duplicates
        item_name = item.get("item", "").lower().strip()
        if item_name in seen_sales:
            errors.append(f"Duplicate sales item: '{item.get('item')}'")
        seen_sales.add(item_name)

    # ── Validate expenses ─────────────────────────────────────────────
    expenses = parsed.get("expenses", [])
    if not isinstance(expenses, list):
        errors.append("'expenses' must be a list.")
        expenses = []

    seen_expenses = set()
    for i, item in enumerate(expenses):
        item_errors = _validate_entry(item, "Expenses", i + 1)
        errors.extend(item_errors)

        item_name = item.get("item", "").lower().strip()
        if item_name in seen_expenses:
            errors.append(f"Duplicate expense item: '{item.get('item')}'")
        seen_expenses.add(item_name)

    # ── Check that we have at least some data ─────────────────────────
    if not sales and not expenses and not errors:
        errors.append("No sales or expense items were found in the data.")

    # ── Result ────────────────────────────────────────────────────────
    is_valid = len(errors) == 0

    if is_valid:
        logger.info(
            f"Validation passed: {len(sales)} sales, {len(expenses)} expenses"
        )
    else:
        logger.warning(f"Validation failed with {len(errors)} errors: {errors}")

    return {
        "is_valid": is_valid,
        "validation_errors": errors,
        "parsed_json": parsed,  # May have been updated (e.g., date default)
    }


def _validate_entry(entry: dict, category: str, index: int) -> list:
    """
    Validate a single sales or expense entry.

    Returns:
        List of error strings (empty if valid).
    """
    errors = []

    if not isinstance(entry, dict):
        errors.append(f"{category} item #{index} is not a valid object.")
        return errors

    # Item name
    item_name = entry.get("item", "")
    if not item_name or not str(item_name).strip():
        errors.append(f"{category} item #{index}: Missing item name.")

    # Amount
    amount = entry.get("amount")
    if amount is None:
        errors.append(f"{category} item #{index} ({item_name}): Missing amount.")
    else:
        try:
            amount_num = float(amount)
            if amount_num < 0:
                errors.append(
                    f"{category} item #{index} ({item_name}): "
                    f"Negative amount (₹{amount_num})."
                )
            if amount_num == 0:
                errors.append(
                    f"{category} item #{index} ({item_name}): "
                    f"Amount is zero."
                )
        except (ValueError, TypeError):
            errors.append(
                f"{category} item #{index} ({item_name}): "
                f"Amount '{amount}' is not a valid number."
            )

    return errors
