import httpx
import asyncio
import config

TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"

async def send_message(chat_id: str | int, message: str):
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        )
        if response.status_code != 200:
            print(f"[Telegram Error] {response.status_code}: {response.text}")
        return response.status_code == 200

async def send_to_all_owners(message: str):
    for chat_id in config.TELEGRAM_OWNER_CHAT_IDS:
        await send_message(chat_id, message)

async def delete_webhook():
    """Hapus webhook agar polling bisa jalan"""
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(f"{TELEGRAM_API}/deleteWebhook")

async def get_updates(offset: int = 0):
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.get(
            f"{TELEGRAM_API}/getUpdates",
            params={"offset": offset, "timeout": 30, "limit": 10}
        )
        if response.status_code == 200:
            return response.json().get("result", [])
        return []

async def send_keyboard(chat_id: str | int, text: str, keyboard: list):
    """Kirim pesan dengan inline keyboard"""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": keyboard}
            }
        )
        if response.status_code != 200:
            print(f"[Telegram Keyboard Error] {response.text}")
        return response.status_code == 200

async def answer_callback(callback_query_id: str):
    """Acknowledge callback query"""
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id}
        )

async def send_reply_keyboard(chat_id: str | int, text: str):
    """Kirim Reply Keyboard permanen"""
    keyboard = {
        "keyboard": [
            [{"text": "💰 Omzet"}, {"text": "📈 Laba Rugi"}],
            [{"text": "💳 Piutang"}, {"text": "📊 Laporan"}],
            [{"text": "📦 Stok"}, {"text": "💲 Harga"}, {"text": "🔧 Modal"}],
            [{"text": "🏆 Terlaris"}]
        ],
        "resize_keyboard": True,
        "persistent": True
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
        )
        return response.status_code == 200

async def send_reply_keyboard_customer(chat_id: str | int, text: str):
    """Keyboard untuk customer — hanya cek harga"""
    keyboard = {
        "keyboard": [
            [{"text": "🔍 Cek Harga Produk"}]
        ],
        "resize_keyboard": True,
        "persistent": True
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
        )
        return response.status_code == 200
