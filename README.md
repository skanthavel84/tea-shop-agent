# 🍵 Tea Shop Accounting Bot

A Telegram bot that acts as a bookkeeping assistant for a tea shop, powered by **LangGraph** for workflow orchestration, **Groq LLM** for intelligent data extraction, **PaddleOCR** for image processing, and **Google Sheets** for persistent storage.

---

## 🏗️ Architecture

```
                 Telegram Bot
                      │
                      ▼
              LangGraph Workflow
                      │
     ┌────────────────┴────────────────┐
     │                                 │
 Receive Message               Conversation State
     │                                 │
     └──────────────┬──────────────────┘
                    ▼
            Detect Intent
                    │
      ┌─────────────┼──────────────┐
      │             │              │
   Add Data       Report         Help
      │             │              │
  OCR (if img)    Read Sheets    Reply
      │             │
  Groq Extract    Summary
      │
  Validate JSON
      │
  ┌───┴───┐
Valid   Invalid
  │       │
Save    Ask User
  │
Summary
  │
Reply
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- A Telegram Bot token (from [@BotFather](https://t.me/BotFather))
- A Groq API key (from [Groq Console](https://console.groq.com/))
- A Google Cloud service account with Sheets API enabled

### 1. Clone & Install

```bash
cd tea-shop-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
GROQ_API_KEY=your-groq-api-key
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_NAME=TeaShopAccounts
```

### 3. Set Up Google Sheets

1. Create a Google Cloud project and enable the **Google Sheets API** and **Google Drive API**
2. Create a service account and download the JSON key file
3. Place it as `credentials.json` in the project root
4. Create a Google Sheet named `TeaShopAccounts` (or your chosen name)
5. Share the sheet with the service account email (found in `credentials.json` as `client_email`)

### 4. Run

```bash
python app.py
```

---

## 🐳 Docker Deployment

```bash
# Build and run
docker compose up -d

# View logs
docker compose logs -f tea-shop-bot
```

---

## 💬 Bot Commands

| Command   | Description                   |
| --------- | ----------------------------- |
| `/start`  | Welcome message               |
| `/help`   | Usage instructions            |
| `/report` | Today's sales/expense summary |

## Usage Examples

**Add Sales:**
```
Tea 150
Coffee 90
Samosa 30
```

**Add Expenses:**
```
Expense: Milk 450, Sugar 200
```

**Send an Image:**
- Send a photo of a handwritten receipt or printed bill
- The bot will OCR the image and extract the data

**Get Report:**
```
Today's report
```

---

## 📂 Project Structure

```
tea-shop-agent/
├── app.py                  # Entry point — Telegram bot + LangGraph
├── graph.py                # LangGraph StateGraph definition
├── state.py                # AgentState TypedDict
├── nodes/                  # Processing nodes
│   ├── receive_message.py  # Parse Telegram update
│   ├── detect_intent.py    # Classify user intent
│   ├── ocr.py              # PaddleOCR image processing
│   ├── groq_extract.py     # Groq LLM data extraction
│   ├── validate.py         # JSON validation
│   ├── sheets.py           # Google Sheets write
│   ├── reports.py          # Report generation
│   └── reply.py            # Telegram reply formatting
├── services/               # External service wrappers
│   ├── groq_client.py      # ChatGroq wrapper
│   ├── google_sheet.py     # gspread wrapper
│   └── telegram_api.py     # Photo download helpers
├── prompts/                # LLM prompt templates
│   └── extraction_prompt.txt
├── config/                 # Configuration
│   └── settings.py         # Environment variable loader
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose config
└── README.md               # This file
```

---

## ⚙️ Technology Stack

| Layer              | Technology                          |
| ------------------ | ----------------------------------- |
| Workflow Engine    | LangGraph (`StateGraph`)            |
| LLM                | Groq (`llama-3.3-70b-versatile`)   |
| LLM Framework      | LangChain (`langchain-groq`)       |
| OCR                | PaddleOCR                           |
| Telegram           | `python-telegram-bot` v21+         |
| Storage            | Google Sheets (`gspread`)          |
| Configuration      | `python-dotenv`                    |
| Deployment         | Docker                              |

---

## 📝 License

MIT
