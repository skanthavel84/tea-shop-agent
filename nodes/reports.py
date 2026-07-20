"""
Report Node — LangGraph ↔ CrewAI Bridge

Generates formatted reports by delegating to the CrewAI Report Crew.
For daily reports, it can use either CrewAI (AI-enhanced) or fallback
to the direct Google Sheets formatter.

Supports:
  - Daily reports (today)
  - Weekly reports (this week / last week)
  - Monthly reports (this month / last month)
  - Custom date range reports
  - Trend analysis and business insights (via CrewAI agents)
"""

import logging
from datetime import date
from collections import defaultdict
from state import AgentState
from services.google_sheet import sheet_service
from services.report_parser import parse_report_request
from services.report_crew import ReportCrew
from config.settings import settings

logger = logging.getLogger(__name__)

# Lazy-initialized singleton for the CrewAI report crew
_report_crew = None


def _get_report_crew() -> ReportCrew:
    """Get or create the singleton ReportCrew instance."""
    global _report_crew
    if _report_crew is None:
        _report_crew = ReportCrew()
    return _report_crew


def _aggregate_items(items: list) -> list:
    """
    Groups a list of items by name (case-insensitive) and sums their amounts.
    Normalizes item names by title-casing them.
    Returns sorted list of dicts: [{'item': name, 'amount': total_amount}]
    """
    totals = defaultdict(float)
    for entry in items:
        name = str(entry.get("item", "Unknown")).strip()
        # Title case to normalize (e.g. "tea" -> "Tea", "milk tea" -> "Milk Tea")
        norm_name = name.title()
        totals[norm_name] += float(entry.get("amount", 0))
    
    return [
        {"item": name, "amount": int(amount) if amount.is_integer() else amount}
        for name, amount in sorted(totals.items(), key=lambda x: x[1], reverse=True)
    ]


def generate_report(state: AgentState) -> dict:
    """
    Generate a report by delegating to the CrewAI Report Crew.

    Parses the user's message to determine the report type and date range,
    then invokes the CrewAI crew for AI-enhanced reporting.

    Falls back to direct formatting if CrewAI fails.

    Returns:
        dict with 'report', 'report_type', 'report_start_date', 'report_end_date'.
    """
    text = state.get("telegram_message", "")

    # Parse the report request to determine type and date range
    report_type, start_date, end_date = parse_report_request(text)
    logger.info(
        f"Report request parsed: type={report_type}, "
        f"range={start_date} to {end_date}"
    )

    try:
        # Invoke CrewAI Report Crew
        crew = _get_report_crew()
        report = crew.run(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
        )

        logger.info(f"CrewAI report generated successfully ({len(report)} chars)")
        return {
            "report": report,
            "report_type": report_type,
            "report_start_date": start_date,
            "report_end_date": end_date,
        }

    except Exception as e:
        logger.error(f"CrewAI report failed, falling back to direct format: {e}")

        # Fallback: use direct Google Sheets formatting (original behavior)
        try:
            if report_type == "daily":
                summary = sheet_service.get_daily_summary(start_date)
                report = _format_report(summary)
            else:
                summary = sheet_service.get_range_summary(start_date, end_date)
                report = _format_range_report(summary)

            logger.info(f"Fallback report generated for {report_type}")
            return {
                "report": report,
                "report_type": report_type,
                "report_start_date": start_date,
                "report_end_date": end_date,
            }

        except Exception as fallback_error:
            logger.error(f"Fallback report also failed: {fallback_error}", exc_info=True)
            return {
                "report": "",
                "error": f"Failed to generate report: {str(fallback_error)}",
                "report_type": report_type,
                "report_start_date": start_date,
                "report_end_date": end_date,
            }


def generate_save_confirmation(state: AgentState) -> dict:
    """
    Generate a confirmation message after saving data.

    Shows what was saved (including branch) and includes a mini-summary.

    Returns:
        dict with 'report' string.
    """
    parsed = state.get("parsed_json", {})
    sales = parsed.get("sales", [])
    expenses = parsed.get("expenses", [])
    branch = parsed.get("branch", "Main")
    record_date = parsed.get("date", date.today().strftime("%Y-%m-%d"))

    lines = [
        f"✅ தரவு வெற்றிகரமாக சேமிக்கப்பட்டது",
    ]

    # Show branch name with ID if available
    branch_id = settings.BRANCH_ID_MAP.get(branch.lower(), "")
    if branch_id:
        lines.append(f"📅 தேதி: {record_date}  |  🏪 கிளை: {branch} (#{branch_id})")
    else:
        lines.append(f"📅 தேதி: {record_date}  |  🏪 கிளை: {branch}")
    lines.append("")

    # Aggregate local entry items
    agg_sales = _aggregate_items(sales)
    agg_expenses = _aggregate_items(expenses)

    if agg_sales:
        lines.append("📈 விற்பனை:")
        total_sales = 0
        for item in agg_sales:
            amount = item.get("amount", 0)
            lines.append(f"  • {item.get('item')} — ₹{amount}")
            total_sales += amount
        lines.append(f"  மொத்த விற்பனை: ₹{total_sales}")
        lines.append("")

    if agg_expenses:
        lines.append("📉 செலவுகள்:")
        total_expenses = 0
        for item in agg_expenses:
            amount = item.get("amount", 0)
            lines.append(f"  • {item.get('item')} — ₹{amount}")
            total_expenses += amount
        lines.append(f"  மொத்த செலவுகள்: ₹{total_expenses}")
        lines.append("")

    if sales and expenses:
        total_sales = sum(i.get("amount", 0) for i in sales)
        total_expenses = sum(i.get("amount", 0) for i in expenses)
        profit = total_sales - total_expenses
        emoji = "💰" if profit >= 0 else "⚠️"
        lines.append(f"{emoji} நிகர லாபம் ({branch}): ₹{profit}")

    report = "\n".join(lines)
    return {"report": report}


# ── Fallback Formatters ───────────────────────────────────────────────
# Used when CrewAI fails; these provide basic formatting without AI insights.


def _format_report(summary: dict) -> str:
    """
    Format a daily summary dict into a readable Telegram message
    with per-branch product breakdowns and grand product totals.

    Args:
        summary: Dict from GoogleSheetService.get_daily_summary()

    Returns:
        Formatted report string.
    """
    report_date = summary.get("date", "Unknown")
    branches = summary.get("branches", {})
    grand_total_sales = summary.get("grand_total_sales", 0)
    grand_total_expenses = summary.get("grand_total_expenses", 0)
    grand_profit = summary.get("grand_profit", 0)

    lines = [
        f"📊 தினசரி அறிக்கை — {report_date}",
        "━" * 30,
        "",
    ]

    if not branches:
        lines.append("📭 இன்றைக்கு தரவு பதிவு செய்யப்படவில்லை.")
        return "\n".join(lines)

    # Track overall items for grand product totals
    all_sales = []
    all_expenses = []

    # Per-branch sections
    for branch_name, data in branches.items():
        b_sales = data.get("sales", [])
        b_expenses = data.get("expenses", [])
        b_total_sales = data.get("total_sales", 0)
        b_total_expenses = data.get("total_expenses", 0)
        b_profit = data.get("profit", 0)

        # Accumulate for grand totals
        all_sales.extend(b_sales)
        all_expenses.extend(b_expenses)

        # Aggregate items per branch
        agg_sales = _aggregate_items(b_sales)
        agg_expenses = _aggregate_items(b_expenses)

        # Show branch name with ID if available
        branch_id = settings.BRANCH_ID_MAP.get(branch_name.lower(), "")
        if branch_id:
            lines.append(f"🏪 கிளை: {branch_name} (#{branch_id})")
        else:
            lines.append(f"🏪 கிளை: {branch_name}")
        lines.append("─" * 26)

        # Sales
        if agg_sales:
            lines.append("  📈 பொருள் வாரி விற்பனை:")
            for item in agg_sales:
                lines.append(f"    • {item['item']} — ₹{item['amount']}")
            lines.append(f"    உப மொத்தம்: ₹{b_total_sales}")
        else:
            lines.append("  📈 விற்பனை: இல்லை")

        # Expenses
        if agg_expenses:
            lines.append("  📉 பொருள் வாரி செலவுகள்:")
            for item in agg_expenses:
                lines.append(f"    • {item['item']} — ₹{item['amount']}")
            lines.append(f"    உப மொத்தம்: ₹{b_total_expenses}")
        else:
            lines.append("  📉 செலவுகள்: இல்லை")

        # Branch profit
        profit_emoji = "💰" if b_profit >= 0 else "📭"
        lines.append(f"  {profit_emoji} லாபம்: ₹{b_profit}")
        lines.append("")

    # Grand totals
    lines.append("━" * 30)
    lines.append("📋 மொத்தம் (அனைத்து கிளைகள்)")
    
    # Grand sales by product
    grand_agg_sales = _aggregate_items(all_sales)
    if grand_agg_sales:
        lines.append("  📈 பொருள் வாரி விற்பனை:")
        for item in grand_agg_sales:
            lines.append(f"    • {item['item']}: ₹{item['amount']}")
    
    # Grand expenses by item
    grand_agg_expenses = _aggregate_items(all_expenses)
    if grand_agg_expenses:
        lines.append("  📉 பொருள் வாரி செலவுகள்:")
        for item in grand_agg_expenses:
            lines.append(f"    • {item['item']}: ₹{item['amount']}")
            
    lines.append("  ─" * 13)
    lines.append(f"  📈 மொத்த விற்பனை:    ₹{grand_total_sales}")
    lines.append(f"  📉 மொத்த செலவுகள்: ₹{grand_total_expenses}")
    grand_emoji = "💰" if grand_profit >= 0 else "📭"
    lines.append(f"  {grand_emoji} நிகர லாபம்:     ₹{grand_profit}")

    return "\n".join(lines)


def _format_range_report(summary: dict) -> str:
    """
    Format a date-range summary dict into a readable Telegram message.
    Used as fallback when CrewAI is unavailable.

    Args:
        summary: Dict from GoogleSheetService.get_range_summary()

    Returns:
        Formatted report string.
    """
    start = summary.get("start_date", "?")
    end = summary.get("end_date", "?")
    branches = summary.get("branches", {})
    daily_totals = summary.get("daily_totals", [])
    grand_total_sales = summary.get("grand_total_sales", 0)
    grand_total_expenses = summary.get("grand_total_expenses", 0)
    grand_profit = summary.get("grand_profit", 0)

    lines = [
        f"📊 காலகட்ட அறிக்கை — {start} முதல் {end} வரை",
        "━" * 30,
        "",
    ]

    if not branches:
        lines.append("📭 இந்த காலகட்டத்தில் தரவு பதிவு செய்யப்படவில்லை.")
        return "\n".join(lines)

    # Per-branch sections
    for branch_name, data in branches.items():
        b_total_sales = data.get("total_sales", 0)
        b_total_expenses = data.get("total_expenses", 0)
        b_profit = data.get("profit", 0)

        # Aggregate items per branch
        agg_sales = _aggregate_items(data.get("sales", []))
        agg_expenses = _aggregate_items(data.get("expenses", []))

        branch_id = settings.BRANCH_ID_MAP.get(branch_name.lower(), "")
        if branch_id:
            lines.append(f"🏪 கிளை: {branch_name} (#{branch_id})")
        else:
            lines.append(f"🏪 கிளை: {branch_name}")
        lines.append("─" * 26)

        if agg_sales:
            lines.append("  📈 பொருள் வாரி விற்பனை:")
            for item in agg_sales:
                lines.append(f"    • {item['item']} — ₹{item['amount']}")
            lines.append(f"    உப மொத்தம்: ₹{b_total_sales}")
        else:
            lines.append("  📈 விற்பனை: இல்லை")

        if agg_expenses:
            lines.append("  📉 பொருள் வாரி செலவுகள்:")
            for item in agg_expenses:
                lines.append(f"    • {item['item']} — ₹{item['amount']}")
            lines.append(f"    உப மொத்தம்: ₹{b_total_expenses}")
        else:
            lines.append("  📉 செலவுகள்: இல்லை")

        profit_emoji = "💰" if b_profit >= 0 else "📭"
        lines.append(f"  {profit_emoji} லாபம்: ₹{b_profit}")
        lines.append("")

    # Daily trend section
    if len(daily_totals) > 1:
        lines.append("━" * 30)
        lines.append("📅 நாள் வாரி போக்கு:")
        for day in daily_totals:
            d = day["date"]
            ds = day["sales"]
            de = day["expenses"]
            dp = day["profit"]
            emoji = "💰" if dp >= 0 else "📭"
            lines.append(f"  {d}: விற்பனை ₹{ds} | செலவு ₹{de} | {emoji} ₹{dp}")
        lines.append("")

    # Grand totals
    lines.append("━" * 30)
    lines.append("📋 மொத்தம் (அனைத்து கிளைகள்)")
    lines.append("  ─" * 13)
    lines.append(f"  📈 மொத்த விற்பனை:    ₹{grand_total_sales}")
    lines.append(f"  📉 மொத்த செலவுகள்: ₹{grand_total_expenses}")
    grand_emoji = "💰" if grand_profit >= 0 else "📭"
    lines.append(f"  {grand_emoji} நிகர லாபம்:     ₹{grand_profit}")

    return "\n".join(lines)
