"""
Скрипт для сравнения результатов бенчмарков до и после оптимизации
Генерирует сравнительную таблицу с улучшениями
"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime


def load_benchmark_results(filepath: str) -> Dict:
    """Загрузить результаты бенчмарка из файла"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def compare_results(before_file: str, after_file: str) -> Dict:
    """
    Сравнить результаты бенчмарков
    
    Args:
        before_file: путь к файлу с результатами ДО оптимизации
        after_file: путь к файлу с результатами ПОСЛЕ оптимизации
        
    Returns:
        Словарь с результатами сравнения
    """
    before_data = load_benchmark_results(before_file)
    after_data = load_benchmark_results(after_file)
    
    # Создаем словарь для быстрого поиска результатов
    before_dict = {}
    for result in before_data['results']:
        key = f"{result['endpoint']}_{result['test_period']}"
        before_dict[key] = result
    
    after_dict = {}
    for result in after_data['results']:
        key = f"{result['endpoint']}_{result['test_period']}"
        after_dict[key] = result
    
    # Сравниваем результаты
    comparison = []
    
    for key in before_dict.keys():
        if key in after_dict:
            before_result = before_dict[key]
            after_result = after_dict[key]
            
            before_time = before_result['avg_time_seconds']
            after_time = after_result['avg_time_seconds']
            
            if before_time > 0:
                improvement = ((before_time - after_time) / before_time) * 100
                speedup = before_time / after_time if after_time > 0 else 0
            else:
                improvement = 0
                speedup = 0
            
            comparison.append({
                'endpoint': before_result['endpoint'],
                'test_period': before_result['test_period'],
                'before_time': before_time,
                'after_time': after_time,
                'improvement_percent': round(improvement, 2),
                'speedup': round(speedup, 2),
                'status': 'improved' if improvement > 0 else 'degraded' if improvement < 0 else 'same'
            })
    
    return {
        'before_timestamp': before_data['timestamp'],
        'after_timestamp': after_data['timestamp'],
        'comparison': comparison
    }


def print_comparison_table(comparison_data: Dict):
    """Вывести сравнительную таблицу"""
    print("\n" + "="*100)
    print("СРАВНИТЕЛЬНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ БЕНЧМАРКА")
    print("="*100)
    print(f"\nДО оптимизации: {comparison_data['before_timestamp']}")
    print(f"ПОСЛЕ оптимизации: {comparison_data['after_timestamp']}")
    print("\n" + "-"*100)
    print(f"{'Эндпоинт':<25} {'Период':<20} {'ДО (с)':<12} {'ПОСЛЕ (с)':<12} {'Улучшение %':<15} {'Ускорение':<12} {'Статус':<10}")
    print("-"*100)
    
    for item in comparison_data['comparison']:
        status_icon = "✓" if item['status'] == 'improved' else "✗" if item['status'] == 'degraded' else "="
        status_text = "Улучшено" if item['status'] == 'improved' else "Ухудшено" if item['status'] == 'degraded' else "Без изменений"
        
        print(f"{item['endpoint']:<25} {item['test_period']:<20} "
              f"{item['before_time']:<12.3f} {item['after_time']:<12.3f} "
              f"{item['improvement_percent']:>+13.2f}% {item['speedup']:>11.2f}x {status_icon} {status_text}")
    
    print("-"*100)
    
    # Итоговая статистика
    improved = sum(1 for item in comparison_data['comparison'] if item['status'] == 'improved')
    degraded = sum(1 for item in comparison_data['comparison'] if item['status'] == 'degraded')
    same = sum(1 for item in comparison_data['comparison'] if item['status'] == 'same')
    
    avg_improvement = sum(item['improvement_percent'] for item in comparison_data['comparison'] if item['status'] == 'improved')
    avg_improvement = avg_improvement / improved if improved > 0 else 0
    
    print(f"\nИтого:")
    print(f"  Улучшено: {improved}")
    print(f"  Ухудшено: {degraded}")
    print(f"  Без изменений: {same}")
    if improved > 0:
        print(f"  Среднее улучшение: {avg_improvement:.2f}%")
    print()


def save_comparison_json(comparison_data: Dict, output_file: str):
    """Сохранить результаты сравнения в JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(comparison_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Результаты сравнения сохранены в {output_file}")


def main():
    """Главная функция"""
    import sys
    
    # Пути к файлам результатов
    before_file = "benchmark_results_before.json"
    after_file = "benchmark_results_with_cache.json"
    
    # Если файлы не найдены, пробуем найти последние
    if not Path(before_file).exists():
        print(f"⚠️  Файл {before_file} не найден")
        # Ищем последний файл с before
        before_files = list(Path(".").glob("benchmark_results_before*.json"))
        if before_files:
            before_file = str(before_files[0])
            print(f"   Используем: {before_file}")
    
    if not Path(after_file).exists():
        print(f"⚠️  Файл {after_file} не найден")
        # Ищем последний файл с after или with_cache
        after_files = list(Path(".").glob("benchmark_results_*cache*.json"))
        if after_files:
            after_file = str(after_files[0])
            print(f"   Используем: {after_file}")
    
    if not Path(before_file).exists() or not Path(after_file).exists():
        print("✗ Не найдены файлы результатов бенчмарка")
        sys.exit(1)
    
    # Сравниваем результаты
    comparison_data = compare_results(before_file, after_file)
    
    # Выводим таблицу
    print_comparison_table(comparison_data)
    
    # Сохраняем в файл
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"benchmark_comparison_{timestamp}.json"
    save_comparison_json(comparison_data, output_file)


if __name__ == "__main__":
    main()

