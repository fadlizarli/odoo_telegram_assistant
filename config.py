import os
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", 8090))

ODOO_URL      = os.getenv("ODOO_URL")
ODOO_DB       = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")

TELEGRAM_TOKEN          = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_OWNER_CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_OWNER_CHAT_IDS", "").split(",") if cid.strip()]
TELEGRAM_CUSTOMER_CHAT_IDS = {}  # {chat_id: odoo_partner_id}

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

DAILY_REPORT_TIME  = os.getenv("DAILY_REPORT_TIME", "21:00")
STOCK_ALERT_LIMIT  = int(os.getenv("STOCK_ALERT_LIMIT", 10))
MEMORY_DB_PATH     = os.getenv("MEMORY_DB_PATH", "/opt/ai-agent/memory.db")
