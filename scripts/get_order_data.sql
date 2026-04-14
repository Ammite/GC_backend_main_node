-- SQL запрос для получения данных для создания примера заказа
-- Выполните этот запрос в вашей БД, чтобы получить данные

-- 1. Пользователь с ID=10
SELECT 
    id,
    name,
    login,
    iiko_id
FROM users
WHERE id = 10;

-- 2. Сотрудник (официант) по iiko_id пользователя
SELECT 
    e.id,
    e.name,
    e.iiko_id
FROM employees e
WHERE e.iiko_id = (SELECT iiko_id FROM users WHERE id = 10)
LIMIT 1;

-- Если сотрудник не найден, берем любого сотрудника
SELECT 
    e.id,
    e.name,
    e.iiko_id
FROM employees e
WHERE e.deleted = false
LIMIT 1;

-- 3. Два случайных товара
SELECT 
    id,
    name,
    price,
    iiko_id
FROM items
WHERE deleted = false
ORDER BY RANDOM()
LIMIT 2;

-- 4. Стол (опционально)
SELECT 
    id,
    number,
    name,
    iiko_id
FROM tables
WHERE is_deleted = false
LIMIT 1;

-- 5. Организация (опционально)
SELECT 
    id,
    name,
    iiko_id
FROM organizations
WHERE is_active = true
LIMIT 1;
