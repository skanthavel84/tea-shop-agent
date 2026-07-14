"""
Google Sheets service wrapper using gspread.

Handles authentication, worksheet auto-creation, and CRUD operations
for the Sales, Expenses, and DailySummary worksheets.
Supports branch-wise data tracking and reporting.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from collections import defaultdict

import gspread
from config.settings import settings

logger = logging.getLogger(__name__)


class GoogleSheetService:
    """Wrapper around gspread for Tea Shop accounting data."""

    # Worksheet names
    SALES_SHEET = "Sales"
    EXPENSES_SHEET = "Expenses"
    SUMMARY_SHEET = "DailySummary"

    # Column headers (with Branch column)
    SALES_HEADERS = ["Date", "Branch", "Item", "Amount", "Timestamp"]
    EXPENSES_HEADERS = ["Date", "Branch", "Item", "Amount", "Timestamp"]
    SUMMARY_HEADERS = ["Date", "Branch", "Total Sales", "Total Expenses", "Profit"]

    def __init__(self):
        self.gc = gspread.service_account(
            filename=settings.GOOGLE_SHEETS_CREDENTIALS_FILE
        )
        self.spreadsheet = self.gc.open(settings.GOOGLE_SHEET_NAME)
        self._ensure_worksheets()

    def _ensure_worksheets(self):
        """Create worksheets with headers if they don't exist, and migrate existing ones."""
        existing = [ws.title for ws in self.spreadsheet.worksheets()]

        for sheet_name, headers in [
            (self.SALES_SHEET, self.SALES_HEADERS),
            (self.EXPENSES_SHEET, self.EXPENSES_HEADERS),
            (self.SUMMARY_SHEET, self.SUMMARY_HEADERS),
        ]:
            if sheet_name not in existing:
                logger.info(f"Creating worksheet: {sheet_name}")
                ws = self.spreadsheet.add_worksheet(
                    title=sheet_name, rows=1000, cols=len(headers)
                )
                ws.append_row(headers)
            else:
                logger.info(f"Worksheet already exists: {sheet_name}. Checking headers...")
                ws = self.spreadsheet.worksheet(sheet_name)
                current_values = ws.get_all_values()
                if current_values:
                    current_headers = current_values[0]
                    if "Branch" not in current_headers:
                        logger.info(f"Migrating worksheet '{sheet_name}' to include 'Branch' column.")
                        new_rows = []
                        # Header row
                        new_headers = current_headers.copy()
                        new_headers.insert(1, "Branch")
                        new_rows.append(new_headers)
                        # Data rows
                        for row in current_values[1:]:
                            new_row = row.copy()
                            # Insert default branch "Main" at index 1
                            if len(new_row) >= 1:
                                new_row.insert(1, "Main")
                            else:
                                new_row.append("Main")
                            new_rows.append(new_row)
                        
                        # Update sheet content
                        ws.clear()
                        ws.update('A1', new_rows)
                        logger.info(f"Successfully migrated worksheet '{sheet_name}'.")

    def _get_worksheet(self, name: str) -> gspread.Worksheet:
        """Get a worksheet by name."""
        return self.spreadsheet.worksheet(name)

    def append_sales(self, sales_data: List[Dict], record_date: str, branch: str = "Main") -> int:
        """
        Append sales rows to the Sales worksheet.

        Args:
            sales_data: List of dicts with 'item' and 'amount' keys.
            record_date: Date string in YYYY-MM-DD format.
            branch: Branch name.

        Returns:
            Number of rows appended.
        """
        ws = self._get_worksheet(self.SALES_SHEET)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows_added = 0

        for entry in sales_data:
            row = [
                record_date,
                branch,
                entry.get("item", "Unknown"),
                entry.get("amount", 0),
                timestamp,
            ]
            ws.append_row(row, value_input_option="USER_ENTERED")
            rows_added += 1
            logger.info(f"Added sale [{branch}]: {entry['item']} ₹{entry['amount']}")

        return rows_added

    def append_expenses(self, expenses_data: List[Dict], record_date: str, branch: str = "Main") -> int:
        """
        Append expense rows to the Expenses worksheet.

        Args:
            expenses_data: List of dicts with 'item' and 'amount' keys.
            record_date: Date string in YYYY-MM-DD format.
            branch: Branch name.

        Returns:
            Number of rows appended.
        """
        ws = self._get_worksheet(self.EXPENSES_SHEET)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows_added = 0

        for entry in expenses_data:
            row = [
                record_date,
                branch,
                entry.get("item", "Unknown"),
                entry.get("amount", 0),
                timestamp,
            ]
            ws.append_row(row, value_input_option="USER_ENTERED")
            rows_added += 1
            logger.info(f"Added expense [{branch}]: {entry['item']} ₹{entry['amount']}")

        return rows_added

    def get_today_sales(self, target_date: Optional[str] = None) -> List[Dict]:
        """
        Get all sales for a given date (defaults to today).

        Returns:
            List of dicts with 'branch', 'item', and 'amount' keys.
        """
        if target_date is None:
            target_date = date.today().strftime("%Y-%m-%d")

        ws = self._get_worksheet(self.SALES_SHEET)
        all_rows = ws.get_all_records()

        return [
            {
                "branch": row.get("Branch", "Main"),
                "item": row["Item"],
                "amount": row["Amount"],
            }
            for row in all_rows
            if row.get("Date") == target_date
        ]

    def get_today_expenses(self, target_date: Optional[str] = None) -> List[Dict]:
        """
        Get all expenses for a given date (defaults to today).

        Returns:
            List of dicts with 'branch', 'item', and 'amount' keys.
        """
        if target_date is None:
            target_date = date.today().strftime("%Y-%m-%d")

        ws = self._get_worksheet(self.EXPENSES_SHEET)
        all_rows = ws.get_all_records()

        return [
            {
                "branch": row.get("Branch", "Main"),
                "item": row["Item"],
                "amount": row["Amount"],
            }
            for row in all_rows
            if row.get("Date") == target_date
        ]

    def get_daily_summary(self, target_date: Optional[str] = None) -> Dict:
        """
        Calculate daily summary for the given date with branch-wise breakdown.

        Returns:
            Dict with 'date', 'branches' (per-branch data), and grand totals.
        """
        if target_date is None:
            target_date = date.today().strftime("%Y-%m-%d")

        sales = self.get_today_sales(target_date)
        expenses = self.get_today_expenses(target_date)

        # Group by branch
        branch_sales = defaultdict(list)
        branch_expenses = defaultdict(list)

        for item in sales:
            branch_sales[item["branch"]].append(
                {"item": item["item"], "amount": item["amount"]}
            )

        for item in expenses:
            branch_expenses[item["branch"]].append(
                {"item": item["item"], "amount": item["amount"]}
            )

        # Build per-branch summaries
        all_branches = sorted(set(list(branch_sales.keys()) + list(branch_expenses.keys())))
        branches = {}
        grand_total_sales = 0
        grand_total_expenses = 0

        for branch in all_branches:
            b_sales = branch_sales.get(branch, [])
            b_expenses = branch_expenses.get(branch, [])
            b_total_sales = sum(item["amount"] for item in b_sales)
            b_total_expenses = sum(item["amount"] for item in b_expenses)
            b_profit = b_total_sales - b_total_expenses

            branches[branch] = {
                "sales": b_sales,
                "expenses": b_expenses,
                "total_sales": b_total_sales,
                "total_expenses": b_total_expenses,
                "profit": b_profit,
            }

            grand_total_sales += b_total_sales
            grand_total_expenses += b_total_expenses

        return {
            "date": target_date,
            "branches": branches,
            "grand_total_sales": grand_total_sales,
            "grand_total_expenses": grand_total_expenses,
            "grand_profit": grand_total_sales - grand_total_expenses,
        }


# Singleton instance
sheet_service = GoogleSheetService()
