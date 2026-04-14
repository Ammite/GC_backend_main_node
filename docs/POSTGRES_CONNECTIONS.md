# Увеличение лимита подключений PostgreSQL

## Проблема

Ошибка: `FATAL: sorry, too many clients already`

Это означает, что достигнут лимит максимального количества одновременных подключений к PostgreSQL.

## Решение

### 1. Проверка текущих настроек

Запустите скрипт для проверки:

```bash
cd /srv/project/backend_main_node
source venv/bin/activate
PYTHONPATH=/srv/project/backend_main_node python scripts/check_postgres_connections.py
```

Или вручную:

```bash
# Подключитесь к PostgreSQL
sudo -u postgres psql

# Проверьте текущее значение
SHOW max_connections;

# Проверьте текущее использование
SELECT count(*) FROM pg_stat_activity;
```

### 2. Увеличение max_connections в PostgreSQL

#### Вариант 1: Через редактирование конфигурационного файла

1. Найдите файл конфигурации PostgreSQL:

```bash
sudo -u postgres psql -c "SHOW config_file;"
```

Обычно это: `/etc/postgresql/*/main/postgresql.conf`

2. Отредактируйте файл:

```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
```

3. Найдите строку `max_connections` и измените её:

```conf
# Было (обычно 100):
max_connections = 100

# Станет (рекомендуется 200-500):
max_connections = 200
```

4. Также проверьте `shared_buffers` (должен быть ~25% от RAM):

```conf
shared_buffers = 256MB  # Для сервера с 1GB RAM
```

5. Перезапустите PostgreSQL:

```bash
sudo systemctl restart postgresql
# Или
sudo service postgresql restart
```

6. Проверьте новое значение:

```bash
sudo -u postgres psql -c "SHOW max_connections;"
```

#### Вариант 2: Через ALTER SYSTEM (PostgreSQL 9.4+)

```bash
sudo -u postgres psql

# Установите новое значение
ALTER SYSTEM SET max_connections = 200;

# Перезагрузите конфигурацию (без перезапуска)
SELECT pg_reload_conf();

# Или перезапустите сервис
# sudo systemctl restart postgresql
```

### 3. Настройки пула подключений SQLAlchemy

В файле `database/database.py` уже настроены следующие параметры:

```python
pool_size=20          # Размер пула подключений
max_overflow=30       # Дополнительные подключения сверх pool_size
pool_pre_ping=True    # Проверка подключения перед использованием
pool_recycle=3600     # Переподключение каждые 3600 секунд (1 час)
```

**Важно:** Максимальное количество подключений от приложения = `pool_size + max_overflow = 20 + 30 = 50`

Убедитесь, что `max_connections` в PostgreSQL больше этого значения (рекомендуется минимум в 2 раза больше).

### 4. Проверка использования подключений

```sql
-- Все подключения
SELECT count(*) as total_connections,
       count(*) FILTER (WHERE state = 'active') as active_connections,
       count(*) FILTER (WHERE state = 'idle') as idle_connections
FROM pg_stat_activity;

-- Подключения по базе данных
SELECT datname, count(*) as connections
FROM pg_stat_activity
GROUP BY datname;

-- Детальная информация о подключениях
SELECT pid, usename, datname, state, query_start, state_change
FROM pg_stat_activity
WHERE datname = 'your_database_name';
```

### 5. Оптимизация использования подключений

#### Проверка утечек подключений

Убедитесь, что все подключения правильно закрываются:

```python
# Правильно - используйте context manager или try/finally
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # Важно!
```

#### Использование connection pooling

SQLAlchemy уже использует пул подключений, но можно дополнительно оптимизировать:

- Уменьшить `pool_size` и `max_overflow`, если не нужны все подключения
- Увеличить `pool_recycle` для долгоживущих подключений
- Использовать `pool_pre_ping=True` для проверки подключений

### 6. Мониторинг

Создайте скрипт для мониторинга подключений:

```bash
# Добавьте в cron для мониторинга
*/5 * * * * /srv/project/backend_main_node/venv/bin/python /srv/project/backend_main_node/scripts/check_postgres_connections.py >> /var/log/postgres_connections.log 2>&1
```

## Рекомендуемые значения

| Параметр | Рекомендуемое значение | Описание |
|----------|----------------------|----------|
| `max_connections` | 200-500 | Зависит от нагрузки |
| `pool_size` | 20 | Размер пула SQLAlchemy |
| `max_overflow` | 30 | Дополнительные подключения |
| `shared_buffers` | 25% RAM | Память для кэширования |

## Дополнительные ресурсы

- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/14/core/pooling.html)

