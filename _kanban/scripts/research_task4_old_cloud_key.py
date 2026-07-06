"""
Проверка: IIKO_OLD_LOGIN_KEY — это запасной активный аккаунт или мусор?

По памяти проекта он «для orders», но в коде сейчас не используется
(в orders_services.py все вызовы идут через CLOUD, не CLOUD_OLD).

Если он работает — узнаем, какие у него организации
(та же сеть или другая инсталляция).

READ-ONLY.
"""
import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

CLOUD_URL = os.getenv("IIKO_OLD_CLOUD_API_URL", "https://api-ru.iiko.services")
OLD_KEY = os.getenv("IIKO_OLD_LOGIN_KEY")
NEW_KEY = os.getenv("IIKO_LOGIN_KEY")


async def get_token(client: httpx.AsyncClient, api_login: str, label: str) -> str:
    print(f"\n--- {label} (apiLogin={api_login[:8]}...) ---")
    r = await client.post(
        f"{CLOUD_URL}/api/1/access_token",
        json={"apiLogin": api_login},
    )
    if r.status_code != 200:
        print(f"  FAILED: HTTP {r.status_code}: {r.text[:200]}")
        return None
    token = r.json().get("token")
    print(f"  OK, token={token[:12]}...")
    return token


async def get_orgs(client: httpx.AsyncClient, token: str, label: str) -> None:
    r = await client.post(
        f"{CLOUD_URL}/api/1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    if r.status_code != 200:
        print(f"  orgs FAILED: HTTP {r.status_code}: {r.text[:300]}")
        return
    orgs = r.json().get("organizations", [])
    print(f"  организаций: {len(orgs)}")
    for o in orgs:
        print(f"    - {o.get('name')!r} (id={o.get('id')})")


async def main() -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        new_token = await get_token(client, NEW_KEY, "NEW key (IIKO_LOGIN_KEY)")
        if new_token:
            await get_orgs(client, new_token, "NEW")

        old_token = await get_token(client, OLD_KEY, "OLD key (IIKO_OLD_LOGIN_KEY)")
        if old_token:
            await get_orgs(client, old_token, "OLD")

        if new_token and old_token:
            print()
            print("=> Оба ключа работают в Cloud. Сравни organizations выше — это одна сеть или две разные?")
        elif old_token and not new_token:
            print("\n=> Только OLD работает. Странно.")
        elif new_token and not old_token:
            print("\n=> Только NEW работает. OLD ключ умер/протух.")
        else:
            print("\n=> Ни один не работает (что не может быть, NEW мы только что использовали).")


if __name__ == "__main__":
    asyncio.run(main())
