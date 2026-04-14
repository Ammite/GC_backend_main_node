# Автоматическая синхронизация через cron

## Эндпоинт для cron: `/sync/cron/sync`

Эндпоинт для автоматической синхронизации данных из iiko API через cron.

### Что делает эндпоинт:

1. **Синхронизация счетов** - обновляет список счетов из iiko
2. **Синхронизация по дате изменения** - получает транзакции, измененные за последние 7 дней, и синхронизирует их
3. **Синхронизация за сегодня** - синхронизирует транзакции и продажи за текущую дату

### Настройка API ключа:

1. Убедитесь, что в `.env` файле установлен `API_VALID_TOKEN`:
```bash
API_VALID_TOKEN=your-secret-api-key-here
```

2. Или установите в `config.py`:
```python
API_VALID_TOKEN = "your-secret-api-key-here"
```

### Установка для cron:

1. Создайте директорию для логов (если её нет):
```bash
mkdir -p /srv/project/backend_main_node/logs
```

2. Откройте crontab для редактирования:
```bash
crontab -e
```

3. Добавьте строку для запуска каждые 3 часа:
```bash
0 */3 * * * curl -X POST "http://localhost:8000/sync/cron/sync?apikey=YOUR_API_KEY_HERE" >> /srv/project/backend_main_node/logs/sync_cron.log 2>&1
```

**ВАЖНО:** Замените `YOUR_API_KEY_HERE` на ваш реальный API ключ из `API_VALID_TOKEN`

### Формат cron:

- `0 */3 * * *` - каждые 3 часа в 0 минут (00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00)
- `0 0,3,6,9,12,15,18,21 * * *` - конкретные часы
- `*/180 * * * *` - каждые 180 минут (3 часа)

### Использование:

#### Вызов через curl:
```bash
curl -X POST "http://localhost:8000/sync/cron/sync?apikey=YOUR_API_KEY_HERE"
```

#### Вызов через wget:
```bash
wget -q -O- --post-data="" "http://localhost:8000/sync/cron/sync?apikey=YOUR_API_KEY_HERE"
```

#### Если сервер на другом хосте/порту:
```bash
curl -X POST "http://your-server:8000/sync/cron/sync?apikey=YOUR_API_KEY_HERE"
```

### Логи:

- Лог из cron: `/srv/project/backend_main_node/logs/sync_cron.log`
- Логи сервера: стандартные логи приложения

### Просмотр логов:

```bash
# Последние 100 строк лога
tail -n 100 /srv/project/backend_main_node/logs/sync_cron.log

# Отслеживание лога в реальном времени
tail -f /srv/project/backend_main_node/logs/sync_cron.log
```

### Проверка работы cron:

```bash
# Проверить, что задача добавлена
crontab -l

# Проверить логи cron (если cron не работает)
grep CRON /var/log/syslog
```

### Тестирование эндпоинта:

```bash
# Тест с правильным API ключом
curl -X POST "http://localhost:8000/sync/cron/sync?apikey=YOUR_API_KEY_HERE"

# Тест с неверным API ключом (должен вернуть 401)
curl -X POST "http://localhost:8000/sync/cron/sync?apikey=wrong-key"
```

### Ответ эндпоинта:

При успешной синхронизации:
```json
{
  "success": true,
  "message": "Автоматическая синхронизация завершена",
  "data": {
    "accounts": {...},
    "modification_sync": {
      "transactions": {...},
      "sales": {...},
      "dates_synced": [...]
    }
  }
}
```

При ошибке:
```json
{
  "success": false,
  "message": "Ошибка автоматической синхронизации: ...",
  "data": null
}
```

---

## Пересчет метрик по сотрудникам

### Эндпоинт: `/recalculate-employee-metrics`

Эндпоинт для пересчета метрик по сотрудникам (таблица `daily_employee_analytics`) за указанный период.

### Что делает эндпоинт:

Пересчитывает агрегированные метрики по сотрудникам:
- Выручка за день
- Количество чеков
- Количество возвратов
- Средний чек

### Параметры:

- `from_date` (optional): Начальная дата в формате "YYYY-MM-DD". Если не указана, используется `to_date` или сегодня.
- `to_date` (optional): Конечная дата в формате "YYYY-MM-DD". Если не указана, используется сегодня.
- `organization_id` (optional): ID организации для фильтрации. Если не указан, пересчитываются метрики для всех организаций.

### Примеры использования:

```bash
# Пересчитать за сегодня
curl -X POST "http://localhost:8000/recalculate-employee-metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Пересчитать за конкретную дату
curl -X POST "http://localhost:8000/recalculate-employee-metrics?to_date=2024-01-15" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Пересчитать за период
curl -X POST "http://localhost:8000/recalculate-employee-metrics?from_date=2024-01-01&to_date=2024-01-31" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Автоматический пересчет через cron:

#### Вариант 1: Использование Python скрипта (рекомендуется)

1. Убедитесь, что скрипт исполняемый:
```bash
chmod +x /srv/project/backend_main_node/scripts/recalculate_employee_metrics_cron.py
```

2. Создайте директорию для логов (если её нет):
```bash
mkdir -p /srv/project/backend_main_node/logs
```

3. Откройте crontab для редактирования:
```bash
crontab -e
```

4. Добавьте строку для запуска каждый день в 02:00:
```bash
0 2 * * * cd /srv/project/backend_main_node && /usr/bin/python3 scripts/recalculate_employee_metrics_cron.py >> logs/recalculate_employee_metrics_cron.log 2>&1
```

**Примечание:** Скрипт пересчитывает метрики за вчерашний день, так как данные за сегодня могут быть еще не полными.

#### Вариант 2: Использование HTTP эндпоинта

```bash
0 2 * * * curl -X POST "http://localhost:8000/recalculate-employee-metrics?to_date=$(date -d yesterday +\%Y-\%m-\%d)" -H "Authorization: Bearer YOUR_TOKEN" >> /srv/project/backend_main_node/logs/recalculate_employee_metrics_cron.log 2>&1
```

### Формат cron:

- `0 2 * * *` - каждый день в 02:00
- `0 3 * * *` - каждый день в 03:00
- `0 2 * * 1` - каждый понедельник в 02:00

### Логи:

- Лог из cron: `/srv/project/backend_main_node/logs/recalculate_employee_metrics_cron.log`
- Логи сервера: стандартные логи приложения

### Просмотр логов:

```bash
# Последние 100 строк лога
tail -n 100 /srv/project/backend_main_node/logs/recalculate_employee_metrics_cron.log

# Отслеживание лога в реальном времени
tail -f /srv/project/backend_main_node/logs/recalculate_employee_metrics_cron.log
```

### Тестирование скрипта:

```bash
# Запуск скрипта вручную
cd /srv/project/backend_main_node
python3 scripts/recalculate_employee_metrics_cron.py
```

### Ответ эндпоинта:

При успешном пересчете:
```json
{
  "success": true,
  "message": "Пересчет метрик по сотрудникам завершен. Обработано 1 дат, 15 сотрудников, ошибок: 0",
  "data": {
    "dates_processed": [
      {
        "date": "2024-01-15",
        "success": true,
        "employees_processed": 15
      }
    ],
    "total_dates": 1,
    "total_employees_processed": 15,
    "errors": null,
    "from_date": "2024-01-15",
    "to_date": "2024-01-15",
    "organization_id": null
  }
}
```

