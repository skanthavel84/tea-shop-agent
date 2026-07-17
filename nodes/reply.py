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
🍵 *டீ கடை கணக்கு பாட்*

கிளைகள் வழியாக உங்கள் டீ கடையின் தினசரி விற்பனை மற்றும் செலவுகளை கண்காணிக்க உதவுகிறேன்!

*பயன்படுத்தும் முறை:*

📈 *விற்பனை சேர்க்க* — பொருட்களை தொகையுடன் அனுப்புங்கள்:
  `டீ 150`
  `காபி 90, சமோசா 30`

📉 *செலவுகள் சேர்க்க* — செலவு அல்லது வாங்கியது என குறிப்பிடுங்கள்:
  `செலவு: பால் 450, சர்க்கரை 200`
  `வாங்கியது கப் 500`

🏪 *கிளை குறிப்பிட* — கிளை ID குறுக்குவழிகள்:
  `b1: டீ 150, காபி 90`
  `#2: செலவு பால் 450`
  `B3: காபி 90, சமோசா 30`
  _(கிளை ID பட்டியல் பார்க்க /branches அழுத்துங்கள்)_
  _(கிளை குறிப்பிடாவிட்டால் "Main" ஆகும்)_

📸 *புகைப்படம்* — ரசீது அல்லது கையால் எழுதிய குறிப்பின் புகைப்படம் அனுப்புங்கள்

📊 *அறிக்கை* — இன்றைய சுருக்கம் கேளுங்கள்:
  `இன்றைய அறிக்கை`
  `சுருக்கம் காட்டு`

*கட்டளைகள்:*
/start — வரவேற்பு செய்தி
/branches — கிளை ID பட்டியல்
/report — இன்றைய சுருக்கம் (அனைத்து கிளைகள்)
/help — இந்த உதவி செய்தி
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
            return {"response": f"❌ அறிக்கை உருவாக்க இயலவில்லை: {error}"}
        else:
            return {"response": "📊 இன்றைய அறிக்கைக்கு தரவு இல்லை."}

    # ── Validation failure ────────────────────────────────────────────
    if is_valid is False:
        error_list = "\n".join(f"  • {e}" for e in validation_errors)
        message = (
            "⚠️ பின்வருவனவற்றை சரிபாருங்கள்:\n\n"
            f"{error_list}\n\n"
            "தரவை திருத்தி மீண்டும் அனுப்புங்கள்."
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
            "response": f"❌ தரவு பிரித்தெடுக்கப்பட்டது ஆனால் சேமிக்க இயலவில்லை:\n{sheet_status}"
        }

    # ── Fallback ──────────────────────────────────────────────────────
    logger.warning("Reply node: no matching condition, sending help")
    return {"response": HELP_MESSAGE}
