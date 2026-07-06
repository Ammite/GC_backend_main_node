"""
Комплексное исследование NEW сервера (gruzin-cuisine-co.iiko.it) после восстановления аккаунта Hamza.
Также тянем Cloud API для сравнения.

Эндпоинты:
  1. Server auth — проверка что Hamza работает
  2. Server payment types — entities/list?rootType=PaymentType
  3. Server departments (corporate tree) — corporation/departments
  4. Server employees — /resto/api/employees
  5. Server salary specification — /resto/api/employees/salary
  6. Cloud payment types — /api/1/payment_types
  7. Cloud terminal groups — /api/1/terminal_groups
  8. Сравнение Cloud vs Server

READ-ONLY. Прямой httpx, не дёргает IikoService, не задевает kill switch.

Запуск:
    cd /srv/project/backend_main_node
    source venv/bin/activate
    python _kanban/scripts/research_new_server_full.py
"""
import asyncio
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
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
OUTPUT_DIR = Path(__file__).parent / "output_new_server"


def banner(title: str) -> None:
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


def fmt_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def save(name: str, data: Any) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.json"
    if isinstance(data, str):
        path.with_suffix(".xml" if data.strip().startswith("<") else ".txt").write_text(data, encoding="utf-8")
    else:
        path.write_text(fmt_json(data), encoding="utf-8")
    print(f"  → saved to {path.name}")


# ============================================================================
# SERVER API helpers
# ============================================================================

async def server_auth(client: httpx.AsyncClient) -> Optional[str]:
    r = await client.get(
        f"{SERVER_URL}/resto/api/auth",
        params={"login": SERVER_LOGIN, "pass": SERVER_PASS},
    )
    if r.status_code != 200:
        print(f"  !! Server auth FAILED: HTTP {r.status_code}: {r.text[:300]}")
        return None
    token = r.text.strip()
    print(f"  OK, token={token[:16]}...")
    return token


async def server_get(client: httpx.AsyncClient, token: str, path: str, label: str, **params) -> Optional[str]:
    params["key"] = token
    try:
        r = await client.get(f"{SERVER_URL}{path}", params=params, timeout=TIMEOUT)
        print(f"  [{label}] HTTP {r.status_code}, {len(r.text)} bytes")
        if r.status_code != 200:
            print(f"    body: {r.text[:300]}")
            return None
        return r.text
    except Exception as e:
        print(f"  [{label}] EXCEPTION: {e}")
        return None


# ============================================================================
# CLOUD API helpers
# ============================================================================

async def cloud_token(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{CLOUD_URL}/api/1/access_token",
        json={"apiLogin": CLOUD_KEY},
    )
    r.raise_for_status()
    return r.json()["token"]


async def cloud_post(client: httpx.AsyncClient, token: str, path: str, body: dict) -> dict:
    r = await client.post(
        f"{CLOUD_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    r.raise_for_status()
    return r.json()


# ============================================================================
# PARSERS
# ============================================================================

def parse_departments_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    result = {"departments": [], "jurpersons": [], "all_items": []}
    for item in root.iter("corporateItemDto"):
        entry = {}
        for child in item:
            if child.text and child.text.strip():
                entry[child.tag] = child.text.strip()
        item_type = entry.get("type", "")
        result["all_items"].append(entry)
        if item_type == "DEPARTMENT":
            result["departments"].append(entry)
        elif item_type == "JURPERSON":
            result["jurpersons"].append(entry)
    return result


def parse_employees_xml(xml_text: str) -> list:
    root = ET.fromstring(xml_text)
    employees = []
    for emp in root.iter("employee"):
        entry = {}
        for child in emp:
            if child.tag == "salarySpecification":
                specs = []
                for spec_child in child:
                    spec = {}
                    for sc in spec_child:
                        spec[sc.tag] = sc.text.strip() if sc.text else None
                    if spec:
                        specs.append(spec)
                entry["salarySpecification"] = specs
            elif child.text and child.text.strip():
                entry[child.tag] = child.text.strip()
        employees.append(entry)
    return employees


def parse_salary_xml(xml_text: str) -> list:
    root = ET.fromstring(xml_text)
    items = []
    for emp in root:
        entry = {}
        for child in emp:
            if len(child) > 0:
                sub = {}
                for sc in child:
                    if len(sc) > 0:
                        subsub = {}
                        for ssc in sc:
                            subsub[ssc.tag] = ssc.text.strip() if ssc.text else None
                        sub[sc.tag] = subsub
                    else:
                        sub[sc.tag] = sc.text.strip() if sc.text else None
                entry[child.tag] = sub
            else:
                entry[child.tag] = child.text.strip() if child.text else None
        items.append(entry)
    return items


# ============================================================================
# MAIN
# ============================================================================

async def main() -> None:
    print(f"Cloud:  {CLOUD_URL}  apiLogin={CLOUD_KEY[:8]}...")
    print(f"Server: {SERVER_URL}  login={SERVER_LOGIN}")
    print()

    async with httpx.AsyncClient(timeout=TIMEOUT, verify=True) as client:

        # ===== 1. SERVER AUTH =====
        banner("1. SERVER AUTH — проверяем что Hamza восстановлен")
        s_token = await server_auth(client)
        if s_token is None:
            print("\n  ⚠ Server всё ещё недоступен. Переходим только к Cloud.")
            server_ok = False
        else:
            server_ok = True

        # ===== 2. SERVER PAYMENT TYPES =====
        server_pt = []
        if server_ok:
            banner("2. SERVER: payment types (entities/list?rootType=PaymentType)")
            raw = await server_get(client, s_token, "/resto/api/v2/entities/list",
                                   "payment_types", rootType="PaymentType", includeDeleted="true")
            if raw:
                server_pt = json.loads(raw)
                save("server_payment_types", server_pt)
                print(f"  Всего: {len(server_pt)} видов оплаты")
                active = [p for p in server_pt if not p.get("deleted")]
                deleted = [p for p in server_pt if p.get("deleted")]
                print(f"  Активных: {len(active)}, удалённых: {len(deleted)}")
                print()
                for pt in active[:5]:
                    print(f"    {pt.get('id','')[:8]}.. | {pt.get('name',''):30} | code={pt.get('code','')}")
                if len(active) > 5:
                    print(f"    ... и ещё {len(active)-5}")

        # ===== 3. SERVER DEPARTMENTS / CORPORATE TREE =====
        departments_data = {}
        if server_ok:
            banner("3. SERVER: departments / corporate tree")
            raw = await server_get(client, s_token, "/resto/api/corporation/departments", "departments")
            if raw:
                save("server_departments_raw", raw)
                departments_data = parse_departments_xml(raw)
                save("server_departments_parsed", departments_data)
                print(f"  Departments: {len(departments_data['departments'])}")
                print(f"  JurPersons:  {len(departments_data['jurpersons'])}")
                for d in departments_data["departments"]:
                    print(f"    DEP: {d.get('id','')[:8]}.. | {d.get('name',''):30} | parent={d.get('parentId','')[:8]}..")
                for j in departments_data["jurpersons"]:
                    print(f"    JUR: {j.get('id','')[:8]}.. | {j.get('name','')}")

        # ===== 4. SERVER EMPLOYEES =====
        server_employees = []
        if server_ok:
            banner("4. SERVER: employees list")
            raw = await server_get(client, s_token, "/resto/api/employees", "employees")
            if raw:
                save("server_employees_raw", raw)
                server_employees = parse_employees_xml(raw)
                save("server_employees_parsed", server_employees)
                print(f"  Всего сотрудников: {len(server_employees)}")
                with_salary = [e for e in server_employees if e.get("salarySpecification")]
                print(f"  С salarySpecification: {len(with_salary)}")
                roles = Counter(e.get("mainRoleCode") for e in server_employees)
                print(f"  Роли: {dict(roles.most_common())}")
                print()
                for e in server_employees[:3]:
                    print(f"    {e.get('id','')[:8]}.. | {e.get('name',''):25} | role={e.get('mainRoleCode','')}")
                    if e.get("salarySpecification"):
                        for s in e["salarySpecification"][:2]:
                            print(f"      salary: {s}")
                if len(server_employees) > 3:
                    print(f"    ... и ещё {len(server_employees)-3}")

        # ===== 5. SERVER SALARY =====
        if server_ok:
            banner("5. SERVER: salary endpoint (/resto/api/employees/salary)")
            raw = await server_get(client, s_token, "/resto/api/employees/salary", "salary")
            if raw:
                save("server_salary_raw", raw)
                salary_data = parse_salary_xml(raw)
                save("server_salary_parsed", salary_data)
                print(f"  Записей: {len(salary_data)}")
                for s in salary_data[:5]:
                    print(f"    {fmt_json(s)[:200]}")

        # ===== 6. SERVER STORES (склады) =====
        if server_ok:
            banner("6. SERVER: stores (склады)")
            raw = await server_get(client, s_token, "/resto/api/corporation/stores", "stores")
            if raw:
                save("server_stores_raw", raw)

        # ===== 7. SERVER GROUPS (группы меню) =====
        if server_ok:
            banner("7. SERVER: product groups")
            raw = await server_get(client, s_token, "/resto/api/v2/entities/list",
                                   "product_groups", rootType="ProductGroup")
            if raw:
                groups = json.loads(raw)
                save("server_product_groups", groups)
                print(f"  Всего групп: {len(groups)}")

        # ===== 8. CLOUD AUTH + ORGS =====
        banner("8. CLOUD: auth + organizations")
        c_token = await cloud_token(client)
        print(f"  OK, token={c_token[:12]}...")

        orgs_resp = await cloud_post(client, c_token, "/api/1/organizations", {})
        orgs = orgs_resp.get("organizations", [])
        save("cloud_organizations", orgs)
        print(f"  Организаций: {len(orgs)}")
        for o in orgs:
            print(f"    {o.get('id','')[:8]}.. | {o.get('name','')}")
        cloud_org_ids = [o["id"] for o in orgs]

        # ===== 9. CLOUD PAYMENT TYPES =====
        banner("9. CLOUD: payment types")
        cloud_pt_raw = await cloud_post(client, c_token, "/api/1/payment_types",
                                        {"organizationIds": cloud_org_ids})
        cloud_pt = cloud_pt_raw.get("paymentTypes", [])
        save("cloud_payment_types", cloud_pt)

        merged: Dict[str, Dict[str, Any]] = {}
        for pt in cloud_pt:
            pid = pt.get("id")
            if not pid:
                continue
            if pid not in merged:
                merged[pid] = dict(pt)
                merged[pid]["terminalGroups"] = list(pt.get("terminalGroups") or [])
            else:
                existing_tg_ids = {tg.get("id") for tg in merged[pid]["terminalGroups"]}
                for tg in pt.get("terminalGroups") or []:
                    if tg.get("id") not in existing_tg_ids:
                        merged[pid]["terminalGroups"].append(tg)

        print(f"  Raw: {len(cloud_pt)}, deduplicated: {len(merged)} unique")

        org_id_to_name = {o["id"]: o.get("name", "") for o in orgs}
        for pid, pt in merged.items():
            tg = pt.get("terminalGroups") or []
            tg_org_ids = sorted({t.get("organizationId") for t in tg if t.get("organizationId")})
            tg_org_names = [org_id_to_name.get(oid, oid)[:20] for oid in tg_org_ids]
            print(f"    {pid[:8]}.. | {pt.get('name',''):30} | {pt.get('paymentTypeKind',''):12} | orgs({len(tg_org_ids)}): {tg_org_names}")

        # ===== 10. CLOUD TERMINAL GROUPS =====
        banner("10. CLOUD: terminal groups")
        tg_resp = await cloud_post(client, c_token, "/api/1/terminal_groups",
                                   {"organizationIds": cloud_org_ids})
        tg_list = tg_resp.get("terminalGroups", [])
        save("cloud_terminal_groups", tg_list)
        for tg_item in tg_list:
            org_id = tg_item.get("organizationId", "")
            org_name = org_id_to_name.get(org_id, org_id)
            items = tg_item.get("items", [])
            print(f"    {org_name:30} → {len(items)} terminal group(s)")
            for ti in items:
                print(f"      - {ti.get('id','')[:8]}.. | {ti.get('name','')}")

        # ===== 11. CLOUD EMPLOYEES =====
        banner("11. CLOUD: employees (couriers endpoint — all employees)")
        try:
            emp_resp = await cloud_post(client, c_token, "/api/1/employees/info",
                                        {"organizationIds": cloud_org_ids})
            cloud_employees = emp_resp
            save("cloud_employees", cloud_employees)
            print(f"  Response keys: {list(cloud_employees.keys())[:10]}")
        except Exception as e:
            print(f"  employees/info error: {e}")

        # ===== 12. COMPARISON: Cloud vs Server =====
        if server_ok and server_pt:
            banner("12. СРАВНЕНИЕ: Cloud vs Server payment types")
            cloud_names = {pt.get("name", "").strip().lower(): pt for pt in merged.values()}
            server_names = {pt.get("name", "").strip().lower(): pt for pt in server_pt if not pt.get("deleted")}

            both = set(cloud_names.keys()) & set(server_names.keys())
            only_cloud = set(cloud_names.keys()) - set(server_names.keys())
            only_server = set(server_names.keys()) - set(cloud_names.keys())

            print(f"  По имени совпадают: {len(both)}")
            print(f"  Только Cloud:  {len(only_cloud)}")
            print(f"  Только Server: {len(only_server)}")

            if both:
                print("\n  --- Совпадающие (UUID разные ожидаемо) ---")
                for name in sorted(both):
                    c = cloud_names[name]
                    s = server_names[name]
                    same_id = "SAME ID" if c.get("id") == s.get("id") else "diff ID"
                    print(f"    '{name}' — cloud={c.get('id','')[:8]}.. server={s.get('id','')[:8]}.. [{same_id}]")

            if only_cloud:
                print(f"\n  --- Только в Cloud ({len(only_cloud)}) ---")
                for name in sorted(only_cloud):
                    pt = cloud_names[name]
                    print(f"    '{name}' | kind={pt.get('paymentTypeKind','')}")

            if only_server:
                print(f"\n  --- Только в Server ({len(only_server)}) ---")
                for name in sorted(only_server):
                    pt = server_names[name]
                    print(f"    '{name}' | code={pt.get('code','')}")

        # ===== SUMMARY =====
        banner("SUMMARY")
        print(f"  Server auth:        {'OK' if server_ok else 'FAILED'}")
        if server_ok:
            print(f"  Server pay types:   {len(server_pt)} ({len([p for p in server_pt if not p.get('deleted')])} active)")
            print(f"  Server departments: {len(departments_data.get('departments', []))}")
            print(f"  Server jurpersons:  {len(departments_data.get('jurpersons', []))}")
            print(f"  Server employees:   {len(server_employees)}")
        print(f"  Cloud organizations: {len(orgs)}")
        print(f"  Cloud pay types:     {len(merged)} unique")
        print(f"\n  All raw data saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
