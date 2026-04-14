import httpx
import logging

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = "8770054212:AAHpl7m8_ST3quLH0pIw5QQDQw_DB1lp-k4"
TELEGRAM_CHAT_ID = "435145574"


async def send_telegram_alert(message: str) -> bool:
    """Отправить уведомление в Telegram. Не бросает исключений — логирует ошибки."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        if len(message) > 4000:
            message = message[:4000] + "\n... (обрезано)"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            })
            if resp.status_code != 200:
                logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
                return False
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False
