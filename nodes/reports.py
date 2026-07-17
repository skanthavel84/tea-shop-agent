"""
Report Node

Generates formatted reports by reading data from Google Sheets.
Supports daily summaries with per-branch breakdowns, item details,
aggregated product-wise summaries, and profit calculations.
"""

import logging
from datetime import date
from collections import defaultdict
from state import AgentState
from services.google_sheet import sheet_service
from config.settings import settings

logger = logging.getLogger(__name__)


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
    Generate a daily summary report with branch-wise breakdown and product-wise totals.

    Reads today's sales and expenses from Google Sheets,
    calculates per-branch totals and profit, and formats a readable report.

    Returns:
        dict with 'report' string.
    """
    try:
        summary = sheet_service.get_daily_summary()
        report = _format_report(summary)
        logger.info(f"Generated branch-wise report for {summary['date']}")
        return {"report": report}

    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        return {
            "report": "",
            "error": f"Failed to generate report: {str(e)}",
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
