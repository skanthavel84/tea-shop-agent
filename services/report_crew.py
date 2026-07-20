"""
CrewAI Report Crew — Multi-Agent Report Generation

Defines a CrewAI crew with 3 specialized agents that work together
to generate comprehensive reports from Google Sheets data:

  1. Data Analyst Agent — Reads and aggregates raw data from Google Sheets
  2. Report Writer Agent — Formats data into a clean Telegram-friendly report
  3. Insight Agent — Analyzes trends and provides actionable insights

The crew uses a sequential process: Data Analyst → Report Writer → Insight Agent.
All agents use ChatGroq via the existing GROQ_API_KEY.
"""

import logging
from crewai import Agent, Task, Crew, Process, LLM
from config.settings import settings
from services.sheets_tools import (
    FetchDailySummaryTool,
    FetchDateRangeSalesTool,
    FetchDateRangeExpensesTool,
    FetchRangeSummaryTool,
)

logger = logging.getLogger(__name__)


class ReportCrew:
    """
    CrewAI crew for generating comprehensive reports.

    Usage:
        crew = ReportCrew()
        result = crew.run(
            report_type="weekly",
            start_date="2026-07-14",
            end_date="2026-07-20",
        )
    """

    def __init__(self):
        """Initialize the ReportCrew with Groq LLM and tools."""
        # Configure the LLM for all agents (reuse existing Groq key)
        self.llm = LLM(
            model=f"groq/{settings.GROQ_MODEL}",
            api_key=settings.GROQ_API_KEY,
            temperature=0.3,
        )

        # Initialize tools
        self.daily_summary_tool = FetchDailySummaryTool()
        self.range_sales_tool = FetchDateRangeSalesTool()
        self.range_expenses_tool = FetchDateRangeExpensesTool()
        self.range_summary_tool = FetchRangeSummaryTool()

        logger.info("ReportCrew initialized with Groq LLM and Google Sheets tools")

    def _create_agents(self):
        """Create the 3 specialized agents for the report crew."""

        # ── Agent 1: Data Analyst ─────────────────────────────────────
        data_analyst = Agent(
            role="Data Analyst",
            goal=(
                "Accurately retrieve and aggregate financial data from Google Sheets "
                "for the requested time period. Ensure all branches and items are captured."
            ),
            backstory=(
                "You are a meticulous data analyst for a tea shop chain. "
                "Your job is to pull sales and expense data from Google Sheets, "
                "organized by branch and date. You never miss a record and always "
                "double-check totals. The data may contain Tamil item names."
            ),
            tools=[
                self.daily_summary_tool,
                self.range_sales_tool,
                self.range_expenses_tool,
                self.range_summary_tool,
            ],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )

        # ── Agent 2: Report Writer ────────────────────────────────────
        report_writer = Agent(
            role="Report Writer",
            goal=(
                "Transform raw financial data into a beautifully formatted, "
                "easy-to-read Telegram message in Tamil with relevant emojis."
            ),
            backstory=(
                "You are a bilingual (Tamil/English) report writer for a tea shop chain. "
                "You create clear, well-structured financial reports that shop owners can "
                "read quickly on Telegram. You use Tamil for labels and headers, "
                "organize data by branch with proper formatting, and always include "
                "totals and profit calculations. You use emojis effectively: "
                "📊 for reports, 🏪 for branches, 📈 for sales, 📉 for expenses, "
                "💰 for profit, 📭 for loss, ━ and ─ for separators."
            ),
            tools=[],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )

        # ── Agent 3: Insight Agent ────────────────────────────────────
        insight_agent = Agent(
            role="Business Insight Analyst",
            goal=(
                "Analyze the financial data to identify trends, patterns, and "
                "actionable business insights. Highlight best sellers, expense "
                "patterns, and profit opportunities."
            ),
            backstory=(
                "You are a sharp business analyst for a tea shop chain. "
                "You look at sales and expense data and quickly spot trends: "
                "which products are selling best, which branches are most profitable, "
                "unusual expense spikes, day-over-day changes, and opportunities "
                "for improvement. You provide insights in concise Tamil with "
                "relevant emojis (💡 for tips, ⬆️ for increases, ⬇️ for decreases, "
                "🏆 for best performers, ⚠️ for concerns)."
            ),
            tools=[],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )

        return data_analyst, report_writer, insight_agent

    def _create_tasks(self, data_analyst, report_writer, insight_agent,
                      report_type: str, start_date: str, end_date: str):
        """Create tasks for each agent based on the report request."""

        # Determine period description for prompts
        if report_type == "daily":
            period_desc = f"today ({start_date})"
            data_instruction = (
                f"Use the fetch_daily_summary tool with target_date='{start_date}' "
                f"to get today's data."
            )
        else:
            period_labels = {
                "weekly": "this week",
                "last_week": "last week",
                "monthly": "this month",
                "last_month": "last month",
                "custom": f"the period {start_date} to {end_date}",
            }
            period_desc = period_labels.get(report_type, f"{start_date} to {end_date}")
            data_instruction = (
                f"Use the fetch_range_summary tool with "
                f"start_date='{start_date}' and end_date='{end_date}' "
                f"to get the aggregated data for this period."
            )

        # ── Task 1: Fetch and aggregate data ──────────────────────────
        data_task = Task(
            description=(
                f"Fetch all financial data for {period_desc} from Google Sheets.\n\n"
                f"Instructions:\n"
                f"1. {data_instruction}\n"
                f"2. Summarize the data clearly: total sales, total expenses, profit "
                f"for each branch, and the grand totals across all branches.\n"
                f"3. List all items sold and expenses incurred with their amounts.\n"
                f"4. If there are multiple days, include daily totals.\n"
                f"5. If there is no data, state that clearly."
            ),
            expected_output=(
                "A detailed data summary with:\n"
                "- Per-branch breakdown (sales items, expense items, totals, profit)\n"
                "- Grand totals across all branches\n"
                "- Daily totals if multi-day report\n"
                "- Raw numbers for the report writer to format"
            ),
            agent=data_analyst,
        )

        # ── Task 2: Format the report ─────────────────────────────────
        report_task = Task(
            description=(
                f"Format the data from the Data Analyst into a beautiful Telegram report.\n\n"
                f"Report period: {period_desc}\n\n"
                f"Formatting rules:\n"
                f"1. Start with: 📊 [report type in Tamil] — [date/period]\n"
                f"2. Use ━ (30 chars) as major separator, ─ (26 chars) as minor separator\n"
                f"3. For each branch, show:\n"
                f"   🏪 கிளை: [BranchName]\n"
                f"   📈 பொருள் வாரி விற்பனை: (itemwise sales with amounts in ₹)\n"
                f"   📉 பொருள் வாரி செலவுகள்: (itemwise expenses with amounts in ₹)\n"
                f"   💰 லாபம்: ₹[profit] (or 📭 if loss)\n"
                f"4. Grand totals section at the end:\n"
                f"   📋 மொத்தம் (அனைத்து கிளைகள்)\n"
                f"   📈 மொத்த விற்பனை: ₹[total]\n"
                f"   📉 மொத்த செலவுகள்: ₹[total]\n"
                f"   💰 நிகர லாபம்: ₹[profit]\n"
                f"5. For multi-day reports, add a daily trends section showing each day's totals\n"
                f"6. Use Tamil for all labels. Keep amounts in ₹ with numbers.\n"
                f"7. If no data exists, show: 📭 இந்த காலகட்டத்தில் தரவு பதிவு செய்யப்படவில்லை.\n"
                f"8. Keep the message under 3500 characters (Telegram limit is 4096)."
            ),
            expected_output=(
                "A formatted Telegram message in Tamil with emojis, branch-wise breakdown, "
                "itemwise details, and grand totals. Ready to send via Telegram."
            ),
            agent=report_writer,
        )

        # ── Task 3: Add insights ──────────────────────────────────────
        insight_task = Task(
            description=(
                f"Analyze the financial data and the formatted report to add business insights.\n\n"
                f"Report period: {period_desc}\n\n"
                f"Instructions:\n"
                f"1. Take the formatted report from the Report Writer.\n"
                f"2. Append an '💡 நுண்ணறிவுகள்' (Insights) section at the end.\n"
                f"3. Include 2-4 actionable insights such as:\n"
                f"   - 🏆 Best selling item(s) and their contribution\n"
                f"   - ⬆️/⬇️ Trends compared to expectations or other days\n"
                f"   - ⚠️ Any concerning patterns (high expenses, low sales days)\n"
                f"   - 💡 Suggestions for improvement\n"
                f"4. Keep insights brief — 1-2 lines each in Tamil.\n"
                f"5. If there's insufficient data for insights, skip this section.\n"
                f"6. Return the COMPLETE report (formatted report + insights section).\n"
                f"7. Do NOT add markdown formatting (no **, no ```). Plain text with emojis only."
            ),
            expected_output=(
                "The complete formatted Telegram report (from Report Writer) with an appended "
                "insights section. The entire message should be under 4000 characters, "
                "formatted as plain text with emojis (no markdown)."
            ),
            agent=insight_agent,
        )

        return [data_task, report_task, insight_task]

    def run(self, report_type: str, start_date: str, end_date: str) -> str:
        """
        Execute the report crew to generate a comprehensive report.

        Args:
            report_type: One of 'daily', 'weekly', 'last_week', 'monthly',
                        'last_month', 'custom'.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.

        Returns:
            Formatted report string ready for Telegram.
        """
        logger.info(
            f"Running ReportCrew: type={report_type}, "
            f"range={start_date} to {end_date}"
        )

        try:
            # Create agents and tasks
            data_analyst, report_writer, insight_agent = self._create_agents()
            tasks = self._create_tasks(
                data_analyst, report_writer, insight_agent,
                report_type, start_date, end_date,
            )

            # Build and run the crew
            crew = Crew(
                agents=[data_analyst, report_writer, insight_agent],
                tasks=tasks,
                process=Process.sequential,
                verbose=True,
            )

            result = crew.kickoff()

            # Extract the final output
            report_text = str(result)

            # Clean up any markdown artifacts the LLM might have added
            report_text = report_text.replace("```", "").strip()

            logger.info(
                f"ReportCrew completed. Output length: {len(report_text)} chars"
            )
            return report_text

        except Exception as e:
            logger.error(f"ReportCrew execution failed: {e}", exc_info=True)
            raise
