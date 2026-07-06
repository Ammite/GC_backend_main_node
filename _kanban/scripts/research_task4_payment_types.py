"""
Research: payment types из Cloud и Server iiko API.

Цель — увидеть «сырые» ответы обоих API на видам оплаты, чтобы понять:
1. Какие поля у Cloud-ответа (terminalGroups, paymentTypeKind, и т.п.).
2. Какие поля у Server-ответа (минимум, без связи с организацией).
3. Какие виды есть, кого мы теряем, у кого пустой scope.
4. Какие юр.лица (JurPerson) реально есть у клиента.

READ-ONLY. Прямой httpx, не дёргает IikoService, не задевает kill switch.
Запуск:
    cd /srv/project/backend_main_node
    source venv/bin/activate
    python _kanban/scripts/research_task4_payment_types.py
"""
import asyncio
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

CLOUD_URL = os.getenv("IIKO_CLOUD_API_URL", "https://api-ru.iiko.services")
CLOUD_KEY = os.getenv("IIKO_LOGIN_KEY")
SERVER_URL = os.getenv("IIKO_SERVER_API_URL")
SERVER_LOGIN = os.getenv("IIKO_SERVER_LOGIN")
SERVER_PASS = os.getenv("IIKO_SERVER_PASSWORD")

TIMEOUT = 30.0


# ============================================================================
# CLOUD API
# ============================================================================

async def cloud_token(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{CLOUD_URL}/api/1/access_token",
        json={"apiLogin": CLOUD_KEY},
    )
    r.raise_for_status()
    return r.json()["token"]


async def cloud_organizations(client: httpx.AsyncClient, token: str) -> List[Dict[str, Any]]:
    r = await client.post(
        f"{CLOUD_URL}/api/1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    r.raise_for_status()
    return r.json().get("organizations", [])


async def cloud_payment_types(
    client: httpx.AsyncClient, token: str, org_ids: List[str]
) -> Dict[str, Any]:
    r = await client.post(
        f"{CLOUD_URL}/api/1/payment_types",
        headers={"Authorization": f"Bearer {token}"},
        json={"organizationIds": org_ids},
    )
    r.raise_for_status()
    return r.json()


# ============================================================================
# SERVER API
# ============================================================================

async def server_token(client: httpx.AsyncClient) -> Optional[str]:
    """Возвращает None при ошибке (например, 401), чтобы не падать.

    iiko Server API ожидает: pass = sha1(password). В .env уже хранится хеш.
    """
    r = await client.get(
        f"{SERVER_URL}/resto/api/auth",
        params={"login": SERVER_LOGIN, "pass": SERVER_PASS},
    )
    if r.status_code != 200:
        print(f"  !! Server auth FAILED: HTTP {r.status_code}: {r.text[:200]}")
        return None
    return r.text.strip()


async def server_payment_types(client: httpx.AsyncClient, token: str) -> List[Dict[str, Any]]:
    r = await client.get(
        f"{SERVER_URL}/resto/api/v2/entities/list",
        params={
            "rootType": "PaymentType",
            "includeDeleted": "true",
            "key": token,
        },
    )
    r.raise_for_status()
    return r.json()


async def server_jur_persons(client: httpx.AsyncClient, token: str) -> List[Dict[str, str]]:
    """Парсим /resto/api/corporation/departments — XML с корп. деревом."""
    r = await client.get(
        f"{SERVER_URL}/resto/api/corporation/departments",
        params={"key": token},
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)

    items = []
    for dep in root.iter("corporateItemDto"):
        type_el = dep.find("type")
        if type_el is None or type_el.text != "JURPERSON":
            continue
        items.append({
            "id": (dep.find("id").text if dep.find("id") is not None else None),
            "name": (dep.find("name").text if dep.find("name") is not None else None),
            "parentId": (dep.find("parentId").text if dep.find("parentId") is not None else None),
        })
    return items


# ============================================================================
# MAIN
# ============================================================================

def banner(title: str) -> None:
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


def fmt_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


async def main() -> None:
    print(f"Cloud:  {CLOUD_URL}  apiLogin={(CLOUD_KEY or '')[:8]}...")
    print(f"Server: {SERVER_URL}  login={SERVER_LOGIN}")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # --- Cloud ---
        banner("1. CLOUD: получаем токен")
        c_token = await cloud_token(client)
        print(f"OK, token={c_token[:12]}...")

        banner("2. CLOUD: список организаций")
        orgs = await cloud_organizations(client, c_token)
        print(f"Всего организаций: {len(orgs)}")
        for o in orgs:
            print(f"  - id={o.get('id')}  name={o.get('name')!r}")
        cloud_org_ids = [o["id"] for o in orgs if o.get("id")]

        banner("3. CLOUD: POST /api/1/payment_types")
        cloud_pt_raw = await cloud_payment_types(client, c_token, cloud_org_ids)
        cloud_pt = cloud_pt_raw.get("paymentTypes", [])
        print(f"Cloud вернул {len(cloud_pt)} записей (с дублированием по terminalGroup)")

        # ===== ДЕДУП =====
        # iiko возвращает одну и ту же оплату для каждого terminalGroup отдельно.
        # Объединяем все terminalGroups одного id вместе.
        merged: Dict[str, Dict[str, Any]] = {}
        for pt in cloud_pt:
            pid = pt.get("id")
            if not pid:
                continue
            if pid not in merged:
                merged[pid] = dict(pt)
                merged[pid]["terminalGroups"] = list(pt.get("terminalGroups") or [])
            else:
                # Аккумулируем terminalGroups
                existing_tg_ids = {tg.get("id") for tg in merged[pid]["terminalGroups"]}
                for tg in pt.get("terminalGroups") or []:
                    if tg.get("id") not in existing_tg_ids:
                        merged[pid]["terminalGroups"].append(tg)

        print(f"После дедупликации: {len(merged)} уникальных видов оплаты")
        print()
        print("--- ОДИН ВИД ЦЕЛИКОМ (для просмотра схемы) ---")
        first_id = next(iter(merged), None)
        if first_id:
            print(fmt_json(merged[first_id]))
        print()
        print("--- УНИКАЛЬНЫЕ ВИДЫ + покрытие организаций ---")
        org_id_to_name = {o["id"]: o.get("name") for o in orgs}
        for pid, pt in merged.items():
            tg = pt.get("terminalGroups") or []
            tg_org_ids = sorted({t.get("organizationId") for t in tg if t.get("organizationId")})
            tg_org_names = [org_id_to_name.get(oid, oid) for oid in tg_org_ids]
            print(
                f"  - {pid[:8]}.. | {pt.get('name'):30} | "
                f"{(pt.get('paymentTypeKind') or '-'):12} | "
                f"orgs: {len(tg_org_ids)}/{len(orgs)}"
            )
            print(f"      → видно в: {tg_org_names if tg_org_names else '(нигде, terminalGroups пуст)'}")

        # Per-org reverse map: какие виды видит каждая организация?
        print()
        print("--- Per-org обратная карта (что видит каждая точка через Cloud) ---")
        org_to_types: Dict[str, List[str]] = {o["id"]: [] for o in orgs}
        for pid, pt in merged.items():
            for t in pt.get("terminalGroups") or []:
                oid = t.get("organizationId")
                if oid in org_to_types:
                    org_to_types[oid].append(pt.get("name") or pid)
        for o in orgs:
            names = sorted(set(org_to_types.get(o["id"], [])))
            print(f"  {o['name']:25} ({len(names)} видов): {names}")

        # --- Server ---
        banner("4. SERVER: получаем токен")
        s_token = await server_token(client)
        if s_token is None:
            print("  Server API недоступен (см. ошибку выше). Пропускаем шаги 5-7 Server.")
            print("  Возможные причины: пароль ротировали, юзер заблокирован, изменился URL.")
            print("  Проверь .env: IIKO_SERVER_LOGIN / IIKO_SERVER_PASSWORD / IIKO_SERVER_API_URL.")
            return
        print(f"OK, token={s_token[:12]}...")

        banner("5. SERVER: GET /resto/api/v2/entities/list?rootType=PaymentType&includeDeleted=true")
        server_pt = await server_payment_types(client, s_token)
        print(f"Server вернул {len(server_pt)} видов оплаты")
        print()
        print("--- ОДИН ВИД ЦЕЛИКОМ (для просмотра схемы) ---")
        if server_pt:
            print(fmt_json(server_pt[0]))
        print()
        print("--- ВСЕ ВИДЫ КРАТКО (id / name / code / deleted) ---")
        for pt in server_pt:
            print(
                f"  - {(pt.get('id') or '')[:8]}.. | "
                f"deleted={str(pt.get('deleted')):5} | "
                f"code={(pt.get('code') or ''):8} | "
                f"name={pt.get('name')!r}"
            )

        banner("6. SERVER: юр.лица (JurPerson)")
        jurs = await server_jur_persons(client, s_token)
        print(f"Всего юр.лиц: {len(jurs)}")
        for j in jurs:
            print(f"  - id={j['id'][:8]}.. parentId={(j.get('parentId') or '')[:8]}.. name={j['name']!r}")

        # --- Анализ ---
        banner("7. АНАЛИЗ: сравнение Cloud vs Server")

        cloud_ids = {pt["id"] for pt in cloud_pt if pt.get("id")}
        server_ids = {pt["id"] for pt in server_pt if pt.get("id")}

        print(f"Cloud:    {len(cloud_ids)} уникальных id")
        print(f"Server:   {len(server_ids)} уникальных id")
        print(f"Пересечение (в обоих): {len(cloud_ids & server_ids)}")
        print(f"Только Cloud:  {len(cloud_ids - server_ids)}")
        print(f"Только Server: {len(server_ids - cloud_ids)}")

        print()
        print("--- Виды ТОЛЬКО в Cloud (если такие есть — странно) ---")
        for pt in cloud_pt:
            if pt["id"] in (cloud_ids - server_ids):
                print(f"  - {pt['name']!r}")

        print()
        print("--- Виды ТОЛЬКО в Server (нет terminalGroup в Cloud — нужны эвристики) ---")
        only_server = [pt for pt in server_pt if pt["id"] in (server_ids - cloud_ids)]
        for pt in only_server:
            print(f"  - deleted={str(pt.get('deleted')):5} code={(pt.get('code') or ''):8} | {pt.get('name')!r}")

        print()
        print("--- Server-only НЕ удалённые, у которых в имени нет упоминания JurPerson ---")
        jur_substrings = []
        for j in jurs:
            name = (j.get("name") or "").strip()
            if name:
                jur_substrings.append(name)
                short_words = [w for w in name.split() if len(w) >= 4]
                jur_substrings.extend(short_words)

        for pt in only_server:
            if pt.get("deleted"):
                continue
            name = pt.get("name") or ""
            hit = any(s.lower() in name.lower() for s in jur_substrings)
            marker = "✓ hint" if hit else "✗ NO hint → ляжет на ВСЕ организации"
            print(f"  [{marker}] {name!r}")

        print()
        print("--- Распределение paymentTypeKind в Cloud-ответе ---")
        kinds = Counter(pt.get("paymentTypeKind") for pt in cloud_pt)
        for k, v in kinds.most_common():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
