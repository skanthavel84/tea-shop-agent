"""
Groq LLM client wrapper using langchain-groq.

Provides a simple interface for calling Groq's LLM with
structured prompts for intent detection and data extraction.
"""

import os
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import settings

logger = logging.getLogger(__name__)


class GroqClient:
    """Wrapper around ChatGroq for the Tea Shop Agent."""

    def __init__(self):
        self.llm = ChatGroq(
            model=settings.GROQ_MODEL,
            temperature=settings.GROQ_TEMPERATURE,
            max_retries=settings.GROQ_MAX_RETRIES,
            api_key=settings.GROQ_API_KEY,
        )
        self._extraction_prompt = self._load_extraction_prompt()

    def _load_extraction_prompt(self) -> str:
        """Load the extraction prompt template from file."""
        prompt_path = os.path.join(
            settings.PROMPTS_DIR, "extraction_prompt.txt"
        )
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Extraction prompt not found at {prompt_path}")
            raise

    def extract_data(self, text: str) -> str:
        """
        Send text to Groq for structured data extraction.

        Args:
            text: The raw text (from user message or OCR) to extract from.

        Returns:
            Raw string response from the LLM (expected to be JSON).
        """
        prompt = self._extraction_prompt.replace("{input_text}", text)

        messages = [
            SystemMessage(content="You are a precise bookkeeping data extractor. The input may be in Tamil (தமிழ்) or English or mixed. Return valid JSON only."),
            HumanMessage(content=prompt),
        ]

        logger.info("Sending extraction request to Groq")
        response = self.llm.invoke(messages)
        logger.debug(f"Groq response: {response.content}")
        return response.content

    def detect_intent(self, text: str) -> str:
        """
        Classify the user's intent from their message text.

        Args:
            text: The user's message text.

        Returns:
            One of: ADD_SALES, ADD_EXPENSES, REPORT, HELP
        """
        messages = [
            SystemMessage(content=(
                "You are an intent classifier for a tea shop accounting bot.\n"
                "The user's message may be in Tamil (தமிழ்), English, or a mix of both.\n"
                "Classify the user's message into exactly one of these intents:\n"
                "- ADD_SALES: User is reporting sales data (items sold with amounts)\n"
                "  Tamil clues: டீ, காபி, விற்பனை, numbers with item names\n"
                "- ADD_EXPENSES: User is reporting expenses (purchases, bills, costs)\n"
                "  Tamil clues: செலவு, வாங்கியது, பில், கொள்முதல்\n"
                "- REPORT: User wants to see a report or summary\n"
                "  Tamil clues: அறிக்கை, சுருக்கம், மொத்தம், இன்றைய\n"
                "- HELP: User is asking for help or has an unrelated question\n"
                "  Tamil clues: உதவி, வணக்கம்\n\n"
                "NOTE: Messages may include a branch name prefix like "
                "'Branch Main:', 'Jayanagar branch:', etc. Ignore the branch prefix "
                "and classify based on the actual content.\n\n"
                "Return ONLY the intent label, nothing else."
            )),
            HumanMessage(content=text),
        ]

        logger.info("Sending intent detection request to Groq")
        response = self.llm.invoke(messages)
        intent = response.content.strip().upper()

        # Validate the response is one of our known intents
        valid_intents = {"ADD_SALES", "ADD_EXPENSES", "REPORT", "HELP"}
        if intent not in valid_intents:
            logger.warning(f"Unknown intent '{intent}', defaulting to HELP")
            return "HELP"

        logger.info(f"Detected intent: {intent}")
        return intent

    def extract_data_strict(self, text: str) -> str:
        """
        Stricter extraction prompt used on retry after initial parse failure.

        Args:
            text: The raw text to extract from.

        Returns:
            Raw string response from the LLM (expected to be JSON).
        """
        messages = [
            SystemMessage(content=(
                "You are a precise bookkeeping data extractor.\n"
                "The input may be in Tamil (தமிழ்) or English or mixed.\n"
                "You MUST return ONLY valid JSON. No markdown, no explanation, no code fences.\n"
                "The JSON must have this exact structure:\n"
                '{"date": "YYYY-MM-DD", "branch": "BranchName", '
                '{"sales": [{"item": "name", "amount": number}], '
                '{"expenses": [{"item": "name", "amount": number}]}\n'
                "If there are no sales, use an empty array. Same for expenses.\n"
                "Use today's date if none is mentioned.\n"
                'If no branch/location is mentioned, use "Main" as the default branch.'
            )),
            HumanMessage(content=f"Extract data from:\n{text}"),
        ]

        logger.info("Sending STRICT extraction request to Groq (retry)")
        response = self.llm.invoke(messages)
        return response.content


# Singleton instance
groq_client = GroqClient()
