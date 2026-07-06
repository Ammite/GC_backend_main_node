"""
Диагностика: какой именно user в iiko Server.

Сейчас в .env:
    IIKO_SERVER_LOGIN=Hamza
    IIKO_SERVER_PASSWORD=7c4a8d09ca3762af61e59520943dc26494f8941b  = sha1("123456")

iiko Server вернул на этот login=Hamza:
    "Пользователь 'Интегратор' удалён из системы"

Странно, что error mention 'Интегратор', а не 'Hamza'. Возможны варианты:
  A. Server игнорирует login и идентифицирует только по password-хешу
  B. На сервере есть alias / маппинг Hamza → Интегратор
  C. Текст ошибки общий — про последнего пытавшегося админа

Проверяем все три, варьируя login. Только GET, всегда тот же pass-хеш.

READ-ONLY.
"""
import asyncio
import os
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SERVER_URL = os.getenv("IIKO_SERVER_API_URL")
SERVER_PASS = os.getenv("IIKO_SERVER_PASSWORD")  # sha1("123456")

# Все логины пробуем с одним и тем же password-хешем
LOGINS_TO_TRY = [
    "Hamza",              # текущий в .env
    "Интегратор",         # из текста ошибки
    "integrator",         # на случай, что транслитерация
    "Integrator",
    "admin",              # типовой дефолт
    "noSuchUserAtAll",    # явно несуществующий — посмотреть какая ошибка
]


async def try_login(client: httpx.AsyncClient, login: str) -> None:
    print(f"\n--- login={login!r} ---")
    try:
        r = await client.get(
            f"{SERVER_URL}/resto/api/auth",
            params={"login": login, "pass": SERVER_PASS},
        )
        print(f"  HTTP {r.status_code}")
        # printable, но без брутфорса — печатаем только первые 300 символов ответа
        print(f"  body: {r.text[:300]!r}")
    except Exception as e:
        print(f"  EXCEPTION: {e}")


async def main() -> None:
    print(f"Server: {SERVER_URL}")
    print(f"Pass hash:  {SERVER_PASS[:10]}... (sha1 от 123456)")

    # Параллельно не делаем, чтобы не спамить — последовательно.
    async with httpx.AsyncClient(timeout=15.0) as client:
        for login in LOGINS_TO_TRY:
            await try_login(client, login)


if __name__ == "__main__":
    asyncio.run(main())
