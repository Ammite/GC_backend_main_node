"""
Скрипт для проверки настроек подключений PostgreSQL
"""
import sys
import os
import psycopg2
from psycopg2 import sql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

def check_postgres_settings():
    """Проверка текущих настроек PostgreSQL"""
    try:
        # Парсим DATABASE_URL
        db_url = config.DATABASE_URL
        if not db_url.startswith("postgresql") and not db_url.startswith("postgres"):
            print("❌ Это не PostgreSQL база данных")
            return
        
        # Извлекаем параметры подключения
        # Формат: postgresql://user:password@host:port/database
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        
        conn_params = {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/") if parsed.path else "postgres",
            "user": parsed.username or "postgres",
            "password": parsed.password or ""
        }
        
        print("=" * 80)
        print("ПРОВЕРКА НАСТРОЕК POSTGRESQL")
        print("=" * 80)
        print(f"Host: {conn_params['host']}")
        print(f"Port: {conn_params['port']}")
        print(f"Database: {conn_params['database']}")
        print(f"User: {conn_params['user']}")
        print("=" * 80)
        
        # Подключаемся к БД
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        
        # Проверяем текущие настройки
        print("\n📊 ТЕКУЩИЕ НАСТРОЙКИ:")
        print("-" * 80)
        
        # max_connections
        cur.execute("SHOW max_connections;")
        max_conn = cur.fetchone()[0]
        print(f"max_connections: {max_conn}")
        
        # Текущее количество подключений
        cur.execute("""
            SELECT count(*) as total_connections,
                   count(*) FILTER (WHERE state = 'active') as active_connections,
                   count(*) FILTER (WHERE state = 'idle') as idle_connections
            FROM pg_stat_activity
            WHERE datname = current_database();
        """)
        stats = cur.fetchone()
        print(f"\nТекущие подключения к БД '{conn_params['database']}':")
        print(f"  Всего: {stats[0]}")
        print(f"  Активных: {stats[1]}")
        print(f"  Простаивающих: {stats[2]}")
        
        # Все подключения
        cur.execute("""
            SELECT count(*) as total_connections
            FROM pg_stat_activity;
        """)
        total_all = cur.fetchone()[0]
        print(f"\nВсего подключений к серверу: {total_all}")
        print(f"Использовано: {total_all} / {max_conn} ({total_all/int(max_conn)*100:.1f}%)")
        
        # Проверяем настройки пула SQLAlchemy
        print("\n📊 НАСТРОЙКИ ПУЛА SQLALCHEMY:")
        print("-" * 80)
        from database.database import engine
        pool = engine.pool
        print(f"pool_size: {pool.size()}")
        print(f"max_overflow: {pool._max_overflow}")
        print(f"pool_pre_ping: {engine.pool._pre_ping}")
        if hasattr(pool, '_recycle'):
            print(f"pool_recycle: {pool._recycle}")
        
        # Рекомендации
        print("\n💡 РЕКОМЕНДАЦИИ:")
        print("-" * 80)
        max_conn_int = int(max_conn)
        if total_all >= max_conn_int * 0.9:
            print("⚠️  ВНИМАНИЕ: Использовано более 90% доступных подключений!")
            print(f"   Рекомендуется увеличить max_connections в PostgreSQL")
            print(f"   Текущее значение: {max_conn}")
            print(f"   Рекомендуемое значение: {max_conn_int * 2}")
        else:
            print("✅ Использование подключений в норме")
        
        if pool.size() + pool._max_overflow > max_conn_int * 0.8:
            print(f"⚠️  ВНИМАНИЕ: Пул SQLAlchemy может использовать до {pool.size() + pool._max_overflow} подключений")
            print(f"   Это составляет {(pool.size() + pool._max_overflow) / max_conn_int * 100:.1f}% от max_connections")
            print(f"   Рекомендуется уменьшить pool_size или max_overflow")
        
        print("\n📝 КАК УВЕЛИЧИТЬ max_connections В POSTGRESQL:")
        print("-" * 80)
        print("1. Отредактируйте файл postgresql.conf:")
        print("   sudo nano /etc/postgresql/*/main/postgresql.conf")
        print(f"   Или: sudo nano $(psql -U postgres -c 'SHOW config_file;' -t)")
        print("\n2. Найдите строку max_connections и измените её:")
        print(f"   max_connections = {max_conn_int * 2}  # Увеличьте в 2 раза")
        print("\n3. Перезапустите PostgreSQL:")
        print("   sudo systemctl restart postgresql")
        print("   Или: sudo service postgresql restart")
        print("\n4. Проверьте новое значение:")
        print("   psql -U postgres -c 'SHOW max_connections;'")
        
        cur.close()
        conn.close()
        
        print("\n✅ Проверка завершена")
        
    except ImportError:
        print("❌ Ошибка: psycopg2 не установлен")
        print("   Установите: pip install psycopg2-binary")
    except psycopg2.OperationalError as e:
        print(f"❌ Ошибка подключения к PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_postgres_settings()

