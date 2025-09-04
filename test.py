import sys
import time
import json
import random
import string

try:
    import requests
except ImportError:
    print("Требуется пакет 'requests'. Установите: pip install requests")
    sys.exit(1)


def random_login(prefix: str = "test_user_") -> str:
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}{int(time.time())}_{suffix}"


def main() -> int:
    base_url = "http://127.0.0.1:8008"
    if len(sys.argv) > 1:
        base_url = sys.argv[1].rstrip('/')

    login = random_login()
    password = "testpass123"

    register_url = f"{base_url}/register"
    login_url = f"{base_url}/login"

    print(f"База URL: {base_url}")
    print(f"Регистрируем пользователя: {login}")

    try:
        r = requests.post(register_url, json={"login": login, "password": password}, timeout=10)
    except Exception as e:
        print(f"Ошибка запроса к {register_url}: {e}")
        return 1

    print(f"/register -> статус {r.status_code}")
    try:
        reg_data = r.json()
    except json.JSONDecodeError:
        print("Некорректный JSON в ответе регистрации")
        return 1
    print("Ответ регистрации:", reg_data)

    if not reg_data.get("success"):
        print("Регистрация неуспешна, тест прерван.")
        return 1

    print("Авторизуемся теми же учетными данными...")
    try:
        r2 = requests.post(login_url, json={"login": login, "password": password}, timeout=10)
    except Exception as e:
        print(f"Ошибка запроса к {login_url}: {e}")
        return 1

    print(f"/login -> статус {r2.status_code}")
    try:
        login_data = r2.json()
    except json.JSONDecodeError:
        print("Некорректный JSON в ответе авторизации")
        return 1
    print("Ответ авторизации:", login_data)

    if not login_data.get("success") or not login_data.get("access_token"):
        print("Авторизация неуспешна или нет токена.")
        return 1

    print("Тест пройден: регистрация и авторизация работают.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


