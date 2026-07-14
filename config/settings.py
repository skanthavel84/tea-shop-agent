"""
Application settings loaded from environment variables.
Uses python-dotenv to load from .env file.
"""

import os
import sys
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


class Settings:
    """Centralised configuration for the Tea Shop Agent."""

    def __init__(self):
        self.TELEGRAM_BOT_TOKEN: str = self._require("TELEGRAM_BOT_TOKEN")
        self.GROQ_API_KEY: str = self._require("GROQ_API_KEY")
        self.GOOGLE_SHEETS_CREDENTIALS_FILE: str = self._require(
            "GOOGLE_SHEETS_CREDENTIALS_FILE"
        )
        self.GOOGLE_SHEET_NAME: str = os.getenv(
            "GOOGLE_SHEET_NAME", "TeaShopAccounts"
        )

        # Groq model configuration
        self.GROQ_MODEL: str = os.getenv(
            "GROQ_MODEL", "llama-3.3-70b-versatile"
        )
        self.GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0"))
        self.GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "2"))

        # OCR configuration
        self.OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "en")
        self.OCR_CONFIDENCE_THRESHOLD: float = float(
            os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.5")
        )

        # Paths
        self.PROMPTS_DIR: str = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "prompts"
        )
        self.TEMP_DIR: str = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "temp"
        )
        os.makedirs(self.TEMP_DIR, exist_ok=True)

    @staticmethod
    def _require(key: str) -> str:
        """Get a required environment variable or exit with an error."""
        value = os.getenv(key)
        if not value:
            print(f"Missing required environment variable: {key}")
            print(f"   Please set it in your .env file. See .env.example")
            sys.exit(1)
        return value


# Singleton instance
settings = Settings()
