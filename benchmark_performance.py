"""
Скрипт для замера производительности эндпоинтов
Измеряет время выполнения запросов до и после оптимизации
"""
import asyncio
import httpx
import time
import json
from datetime import datetime
from typing import Dict, List, Tuple
import sys

# Базовый URL API
BASE_URL = "http://localhost:8008"

# Эндпоинты для тестирования
ENDPOINTS = [
    {
        "name": "analytics",
        "path": "/analytics",
        "params": {}
    },
    {
        "name": "reports_orders",
        "path": "/reports/orders",
        "params": {}
    },
    {
        "name": "reports_moneyflow",
        "path": "/reports/moneyflow",
        "params": {}
    },
    {
        "name": "reports_profit_loss",
        "path": "/reports/profit-loss",
        "params": {}
    },
    {
        "name": "reports_expenses",
        "path": "/reports/expenses",
        "params": {}
    }
]

# Периоды для тестирования
TEST_PERIODS = [
    {
        "name": "day_02_12_2025",
        "date": "02.12.2025",
        "period": "day"
    },
    {
        "name": "week_23_11_2025",
        "date": "23.11.2025",
        "period": "week"
    }
]


async def measure_endpoint(
    client: httpx.AsyncClient,
    endpoint: Dict,
    test_period: Dict,
    iterations: int = 3
) -> Dict:
    """
    Измерить время выполнения эндпоинта
    
    Args:
        client: HTTP клиент
        endpoint: информация об эндпоинте
        test_period: период тестирования
        iterations: количество итераций для усреднения
        
    Returns:
        Словарь с результатами измерения
    """
    url = f"{BASE_URL}{endpoint['path']}"
    params = {
        **endpoint['params'],
        "date": test_period["date"],
        "period": test_period["period"]
    }
    
    times = []
    errors = []
    
    for i in range(iterations):
        try:
            start_time = time.time()
            response = await client.get(url, params=params, timeout=300.0)
            end_time = time.time()
            
            elapsed = end_time - start_time
            times.append(elapsed)
            
            if response.status_code != 200:
                errors.append(f"Iteration {i+1}: HTTP {response.status_code}")
                print(f"  ⚠️  Итерация {i+1}: HTTP {response.status_code}")
            else:
                print(f"  ✓ Итерация {i+1}: {elapsed:.3f}s")
                
        except Exception as e:
            error_msg = f"Iteration {i+1}: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ {error_msg}")
    
    avg_time = sum(times) / len(times) if times else 0
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0
    
    return {
        "endpoint": endpoint["name"],
        "path": endpoint["path"],
        "test_period": test_period["name"],
        "date": test_period["date"],
        "period": test_period["period"],
        "iterations": iterations,
        "successful_iterations": len(times),
        "avg_time_seconds": round(avg_time, 3),
        "min_time_seconds": round(min_time, 3),
        "max_time_seconds": round(max_time, 3),
        "errors": errors,
        "all_times": [round(t, 3) for t in times]
    }


async def run_benchmark(iterations: int = 3) -> List[Dict]:
    """
    Запустить бенчмарк для всех эндпоинтов и периодов
    
    Args:
        iterations: количество итераций для каждого эндпоинта
        
    Returns:
        Список результатов измерений
    """
    results = []
    
    async with httpx.AsyncClient() as client:
        # Проверяем доступность API
        try:
            response = await client.get(f"{BASE_URL}/docs", timeout=5.0)
            print(f"✓ API доступен по адресу {BASE_URL}\n")
        except Exception as e:
            print(f"✗ Ошибка подключения к API: {e}")
            print(f"  Убедитесь, что сервер запущен на {BASE_URL}\n")
            return results
        
        total_tests = len(ENDPOINTS) * len(TEST_PERIODS)
        current_test = 0
        
        for endpoint in ENDPOINTS:
            for test_period in TEST_PERIODS:
                current_test += 1
                print(f"[{current_test}/{total_tests}] Тестирую {endpoint['name']} ({test_period['name']})...")
                
                result = await measure_endpoint(client, endpoint, test_period, iterations)
                results.append(result)
                
                print(f"  Среднее время: {result['avg_time_seconds']:.3f}s (мин: {result['min_time_seconds']:.3f}s, макс: {result['max_time_seconds']:.3f}s)\n")
                
                # Небольшая пауза между запросами
                await asyncio.sleep(0.5)
    
    return results


def save_results(results: List[Dict], filename: str = None):
    """
    Сохранить результаты в файл
    
    Args:
        results: результаты измерений
        filename: имя файла (если None, генерируется автоматически)
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_results_{timestamp}.json"
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "results": results
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Результаты сохранены в {filename}")
    return filename


def print_summary(results: List[Dict]):
    """
    Вывести сводку результатов
    
    Args:
        results: результаты измерений
    """
    print("\n" + "="*80)
    print("СВОДКА РЕЗУЛЬТАТОВ")
    print("="*80 + "\n")
    
    # Группируем по эндпоинтам
    by_endpoint = {}
    for result in results:
        endpoint = result["endpoint"]
        if endpoint not in by_endpoint:
            by_endpoint[endpoint] = []
        by_endpoint[endpoint].append(result)
    
    for endpoint, endpoint_results in by_endpoint.items():
        print(f"📊 {endpoint.upper()}")
        print("-" * 80)
        
        for result in endpoint_results:
            period_name = result["test_period"]
            avg_time = result["avg_time_seconds"]
            min_time = result["min_time_seconds"]
            max_time = result["max_time_seconds"]
            
            print(f"  {period_name:30s} | Среднее: {avg_time:6.3f}s | Мин: {min_time:6.3f}s | Макс: {max_time:6.3f}s")
        
        print()


async def main():
    """Главная функция"""
    print("="*80)
    print("БЕНЧМАРК ПРОИЗВОДИТЕЛЬНОСТИ ЭНДПОИНТОВ")
    print("="*80)
    print(f"\nБазовый URL: {BASE_URL}")
    print(f"Количество итераций на эндпоинт: 3")
    print(f"Всего тестов: {len(ENDPOINTS) * len(TEST_PERIODS)}\n")
    
    try:
        results = await run_benchmark(iterations=3)
        
        if results:
            print_summary(results)
            filename = save_results(results)
            print(f"\n✓ Бенчмарк завершен. Результаты сохранены в {filename}")
        else:
            print("\n✗ Не удалось выполнить бенчмарк")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Бенчмарк прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Ошибка при выполнении бенчмарка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

