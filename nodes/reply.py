"""
Reply Node

Formats the final response and prepares it for sending via Telegram.
The actual sending is done by the Telegram handler in app.py after
the graph completes.
"""

import logging
from state import AgentState

logger = logging.getLogger(__name__)

HELP_MESSAGE = """
🍵 *Tea Shop Accounting Bot*

I can help you track your tea shop's daily sales and expenses across branches!

*How to use:*

📈 *Add Sales* — Send items with amounts:
  `Tea 150`
  `Coffee 90, Samosa 30`

📉 *Add Expenses* — Mention costs or purchases:
  `Expense: Milk 450, Sugar 200`
  `Bought Cups 500`

🏪 *Specify Branch* — Include branch name:
  `Branch Main: Tea 150, Coffee 90`
  `Jayanagar branch: Expense Milk 450`
  _(Defaults to "Main" if not specified)_

📸 *Image* — Send a photo of a receipt or handwritten note

📊 *Report* — Ask for today's summary:
  `Today's report`
  `Show summary`

*Commands:*
/start — Welcome message
/report — Today's summary (all branches)
/help — This help message
""".strip()


def reply(state: AgentState) -> dict:
    """
    Build the final response message based on the current state.

    Determines the appropriate response by checking:
      1. Errors → error message
      2. Validation failures → correction request
      3. Report available → report
      4. Default → help message

    Returns:
        dict with 'response' string.
    """
    intent = state.get("intent", "")
    error = state.get("error", "")
    is_valid = state.get("is_valid", None)
    validation_errors = state.get("validation_errors", [])
    report = state.get("report", "")
    sheet_status = state.get("sheet_status", "")

    # ── Error from any node ───────────────────────────────────────────
    if error and intent != "REPORT":
        logger.info("Replying with error message")
        return {"response": f"❌ {error}"}

    # ── HELP intent ───────────────────────────────────────────────────
    if intent == "HELP":
        logger.info("Replying with help message")
        return {"response": HELP_MESSAGE}

    # ── REPORT intent ─────────────────────────────────────────────────
    if intent == "REPORT":
        if report:
            logger.info("Replying with report")
            return {"response": report}
        elif error:
            return {"response": f"❌ Could not generate report: {error}"}
        else:
            return {"response": "📊 No data available for today's report."}

    # ── Validation failure ────────────────────────────────────────────
    if is_valid is False:
        error_list = "\n".join(f"  • {e}" for e in validation_errors)
        message = (
            "⚠️ Please verify the following:\n\n"
            f"{error_list}\n\n"
            "Please correct and resend your data."
        )
        logger.info(f"Replying with validation errors ({len(validation_errors)})")
        return {"response": message}

    # ── Successful save ───────────────────────────────────────────────
    if report and sheet_status == "success":
        logger.info("Replying with save confirmation")
        return {"response": report}

    # ── Sheet write error ─────────────────────────────────────────────
    if sheet_status and sheet_status != "success":
        return {
            "response": f"❌ Data was extracted but could not be saved:\n{sheet_status}"
        }

    # ── Fallback ──────────────────────────────────────────────────────
    logger.warning("Reply node: no matching condition, sending help")
    return {"response": HELP_MESSAGE}
