# API Guide для Frontend разработчиков

Полное руководство по работе с API endpoints для интеграции с фронтендом.

## 📋 Содержание

- [Базовая настройка](#базовая-настройка)
- [Авторизация](#авторизация)
- [Квесты](#квесты)
- [Зарплата](#зарплата)
- [Аналитика](#аналитика)
- [Отчеты](#отчеты)
- [Смены](#смены)
- [Помещения и Столы](#помещения-и-столы)
- [Сотрудники](#сотрудники)
- [Обработка ошибок](#обработка-ошибок)

---

## 🔧 Базовая настройка

### Base URL
```javascript
const BASE_URL = 'http://localhost:8008';
// или для продакшена
const BASE_URL = 'https://your-domain.com';
```

### Axios конфигурация
```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Добавляем токен к каждому запросу
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

---

## 🔐 Авторизация

Все endpoints требуют авторизации. Есть два способа:

### Способ 1: Bearer Token (рекомендуется)
```javascript
headers: {
  'Authorization': `Bearer ${token}`
}
```

### Способ 2: Query параметр
```javascript
const url = `/endpoint?token=${apiToken}`;
```

---

## 🎯 Квесты

### 1. Получить квесты официанта

**Endpoint:** `GET /waiter/{waiterId}/quests`

**Когда использовать:** Для отображения квестов на странице официанта

```javascript
// Функция для получения квестов
async function getWaiterQuests(waiterId, date = null, organizationId = null) {
  try {
    const params = {};
    if (date) params.date = date; // формат: "15.01.2025"
    if (organizationId) params.organization_id = organizationId;
    
    const response = await api.get(`/waiter/${waiterId}/quests`, { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения квестов:', error);
    throw error;
  }
}

// Пример использования
const quests = await getWaiterQuests(1, '15.01.2025');
console.log(quests);
```

**Ответ:**
```json
{
  "quests": [
    {
      "id": "1",
      "title": "Квест на сегодня",
      "description": "Продай 15 десерт",
      "reward": 15000,
      "current": 3,
      "target": 15,
      "unit": "десерт",
      "completed": false,
      "progress": 20.0,
      "expiresAt": "2025-01-15T23:59:59Z"
    }
  ]
}
```

**Пример компонента React:**
```jsx
import { useState, useEffect } from 'react';

function WaiterQuests({ waiterId }) {
  const [quests, setQuests] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchQuests() {
      try {
        const data = await getWaiterQuests(waiterId);
        setQuests(data.quests);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }
    fetchQuests();
  }, [waiterId]);

  if (loading) return <div>Загрузка...</div>;

  return (
    <div className="quests">
      {quests.map(quest => (
        <div key={quest.id} className="quest-card">
          <h3>{quest.title}</h3>
          <p>{quest.description}</p>
          <div className="progress">
            <div className="progress-bar" style={{ width: `${quest.progress}%` }} />
            <span>{quest.current} / {quest.target}</span>
          </div>
          <p className="reward">Награда: {quest.reward.toLocaleString()} тг</p>
          {quest.completed && <span className="badge">✅ Выполнено</span>}
        </div>
      ))}
    </div>
  );
}
```

### 2. Получить детали квеста (для CEO)

**Endpoint:** `GET /quests/{questId}`

**Когда использовать:** Для просмотра прогресса всех сотрудников по квесту

```javascript
async function getQuestDetails(questId, organizationId = null) {
  try {
    const params = organizationId ? { organization_id: organizationId } : {};
    const response = await api.get(`/quests/${questId}`, { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения деталей квеста:', error);
    throw error;
  }
}

// Использование
const questDetails = await getQuestDetails(1);
```

**Ответ:**
```json
{
  "id": "1",
  "title": "Квест на сегодня",
  "description": "Продай 15 десерт",
  "reward": 15000,
  "current": 10,
  "target": 15,
  "unit": "десерт",
  "completed": false,
  "progress": 66.67,
  "expiresAt": "2025-01-15T23:59:59Z",
  "totalEmployees": 5,
  "completedEmployees": 2,
  "employeeNames": ["Аслан Аманов", "Аида Таманова"],
  "date": "15.01.2025",
  "employeeProgress": [
    {
      "employeeId": "1",
      "employeeName": "Аслан Аманов",
      "progress": 100.0,
      "completed": true,
      "points": 15,
      "rank": 1
    }
  ]
}
```

### 3. Создать квест (для CEO)

**Endpoint:** `POST /quests`

**Когда использовать:** Для создания нового квеста

```javascript
async function createQuest(questData) {
  try {
    const response = await api.post('/quests', questData);
    return response.data;
  } catch (error) {
    console.error('Ошибка создания квеста:', error);
    throw error;
  }
}

// Пример использования
const newQuest = await createQuest({
  title: "Продай 15 десерт",
  description: "Продай 15 десерт за смену",
  reward: 15000,
  target: 15,
  unit: "десерт",
  date: "15.01.2025",
  employeeIds: ["1", "2", "3"], // опционально
  organization_id: 1 // опционально
});
```

**Пример формы:**
```jsx
function CreateQuestForm() {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    reward: 0,
    target: 0,
    unit: '',
    date: new Date().toLocaleDateString('ru-RU'),
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const result = await createQuest(formData);
      alert('Квест создан успешно!');
    } catch (error) {
      alert('Ошибка создания квеста');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Название"
        value={formData.title}
        onChange={(e) => setFormData({...formData, title: e.target.value})}
      />
      <input
        type="number"
        placeholder="Целевое значение"
        value={formData.target}
        onChange={(e) => setFormData({...formData, target: Number(e.target.value)})}
      />
      <input
        type="number"
        placeholder="Награда (тг)"
        value={formData.reward}
        onChange={(e) => setFormData({...formData, reward: Number(e.target.value)})}
      />
      <button type="submit">Создать квест</button>
    </form>
  );
}
```

---

## 💰 Зарплата

### Получить зарплату официанта

**Endpoint:** `GET /waiter/{waiterId}/salary`

**Когда использовать:** Для отображения зарплаты официанта за день

```javascript
async function getWaiterSalary(waiterId, date, organizationId = null) {
  try {
    const params = { date }; // формат: "15.01.2025"
    if (organizationId) params.organization_id = organizationId;
    
    const response = await api.get(`/waiter/${waiterId}/salary`, { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения зарплаты:', error);
    throw error;
  }
}

// Использование
const salary = await getWaiterSalary(1, '15.01.2025');
```

**Ответ:**
```json
{
  "date": "15.01.2025",
  "tablesCompleted": 39,
  "totalRevenue": 1000192,
  "salary": 58192,
  "salaryPercentage": 5.0,
  "bonuses": 5157,
  "questBonus": 15000,
  "questDescription": "Бонус за выполнение квеста: Продай 15 десерт",
  "penalties": 0,
  "totalEarnings": 78349,
  "breakdown": {
    "baseSalary": 50035,
    "percentage": 5.0,
    "bonuses": [
      {
        "type": "performance",
        "amount": 5157,
        "description": "Бонус за отличную работу"
      }
    ],
    "penalties": [],
    "questRewards": [
      {
        "questId": "1",
        "questName": "Продай 15 десерт",
        "reward": 15000
      }
    ]
  },
  "quests": [...]
}
```

**Пример компонента:**
```jsx
function SalaryCard({ waiterId, date }) {
  const [salary, setSalary] = useState(null);

  useEffect(() => {
    getWaiterSalary(waiterId, date).then(setSalary);
  }, [waiterId, date]);

  if (!salary) return <div>Загрузка...</div>;

  return (
    <div className="salary-card">
      <h2>Зарплата за {salary.date}</h2>
      
      <div className="summary">
        <div className="stat">
          <span>Столов обслужено:</span>
          <strong>{salary.tablesCompleted}</strong>
        </div>
        <div className="stat">
          <span>Выручка:</span>
          <strong>{salary.totalRevenue.toLocaleString()} тг</strong>
        </div>
        <div className="stat">
          <span>Базовая зарплата ({salary.salaryPercentage}%):</span>
          <strong>{salary.salary.toLocaleString()} тг</strong>
        </div>
      </div>

      <div className="earnings">
        <div className="bonus">
          <span>Бонусы:</span>
          <strong className="positive">+{salary.bonuses.toLocaleString()} тг</strong>
        </div>
        <div className="quest-bonus">
          <span>Бонус за квесты:</span>
          <strong className="positive">+{salary.questBonus.toLocaleString()} тг</strong>
        </div>
        {salary.penalties > 0 && (
          <div className="penalties">
            <span>Штрафы:</span>
            <strong className="negative">-{salary.penalties.toLocaleString()} тг</strong>
          </div>
        )}
      </div>

      <div className="total">
        <span>Итого:</span>
        <strong>{salary.totalEarnings.toLocaleString()} тг</strong>
      </div>
    </div>
  );
}
```

---

## 📊 Аналитика

### Получить аналитику (для CEO)

**Endpoint:** `GET /analytics`

**Когда использовать:** Для дашборда CEO с общей аналитикой

```javascript
async function getAnalytics(date = null, period = 'day', organizationId = null) {
  try {
    const params = { period };
    if (date) params.date = date; // формат: "15.01.2025"
    if (organizationId) params.organization_id = organizationId;
    
    const response = await api.get('/analytics', { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения аналитики:', error);
    throw error;
  }
}

// Использование
const analytics = await getAnalytics('15.01.2025', 'day');
```

**Параметры:**
- `date` (optional): "DD.MM.YYYY"
- `period` (optional): "day" | "week" | "month"
- `organization_id` (optional): число

**Ответ:**
```json
{
  "metrics": [
    {
      "id": 1,
      "label": "Выручка",
      "value": "19 589 699 тг",
      "change": {
        "value": "+21%",
        "trend": "up"
      }
    },
    {
      "id": 2,
      "label": "Чеки",
      "value": "1240",
      "change": {
        "value": "-5%",
        "trend": "down"
      }
    },
    {
      "id": 3,
      "label": "Средний чек",
      "value": "15 800 тг",
      "change": {
        "value": "+15%",
        "trend": "up"
      }
    }
  ],
  "reports": [
    {
      "id": 1,
      "title": "Итого Расходы",
      "value": "+13 712 789 тг",
      "date": "15.01",
      "type": "expense"
    }
  ],
  "orders": [
    {
      "id": 1,
      "label": "Средний чек",
      "value": "15 800 тг"
    },
    {
      "id": 2,
      "label": "Сумма возвратов",
      "value": "-15 800 тг",
      "type": "negative"
    }
  ],
  "financial": [
    {
      "id": 1,
      "label": "Сумма всех проданных блюд по себестоимости",
      "value": "5 876 910 тг"
    }
  ],
  "inventory": [
    {
      "id": 1,
      "label": "Сумма товаров на начало периода",
      "value": "11 753 820 тг"
    }
  ],
  "employees": [
    {
      "id": 1,
      "name": "Аслан Аманов",
      "amount": "1 234 567 тг",
      "avatar": "https://..."
    }
  ]
}
```

**Пример компонента:**
```jsx
function AnalyticsDashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [period, setPeriod] = useState('day');

  useEffect(() => {
    getAnalytics(null, period).then(setAnalytics);
  }, [period]);

  if (!analytics) return <div>Загрузка...</div>;

  return (
    <div className="analytics-dashboard">
      {/* Переключатель периода */}
      <div className="period-selector">
        <button onClick={() => setPeriod('day')}>День</button>
        <button onClick={() => setPeriod('week')}>Неделя</button>
        <button onClick={() => setPeriod('month')}>Месяц</button>
      </div>

      {/* Основные метрики */}
      <div className="metrics-grid">
        {analytics.metrics.map(metric => (
          <div key={metric.id} className="metric-card">
            <span className="label">{metric.label}</span>
            <h3>{metric.value}</h3>
            {metric.change && (
              <span className={`change ${metric.change.trend}`}>
                {metric.change.value}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Топ сотрудников */}
      <div className="top-employees">
        <h3>Топ сотрудников</h3>
        {analytics.employees.map(emp => (
          <div key={emp.id} className="employee-item">
            <img src={emp.avatar} alt={emp.name} />
            <span>{emp.name}</span>
            <strong>{emp.amount}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 📈 Отчеты

### 1. Отчеты по заказам

**Endpoint:** `GET /reports/orders`

```javascript
async function getOrderReports(date, period = 'day', organizationId = null) {
  try {
    const params = { date, period };
    if (organizationId) params.organization_id = organizationId;
    
    const response = await api.get('/reports/orders', { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения отчетов по заказам:', error);
    throw error;
  }
}

// Использование
const orderReports = await getOrderReports('15.01.2025', 'day');
```

**Ответ:**
```json
{
  "checks": {
    "id": 12332,
    "label": "Средний чек",
    "value": "15 800 тг"
  },
  "returns": {
    "id": 31341,
    "label": "Сумма возвратов",
    "value": "-15 800 тг",
    "type": "negative"
  },
  "averages": [
    {
      "id": 1,
      "label": "Среднее количество",
      "value": "3 блюда"
    },
    {
      "id": 2,
      "label": "Популярные блюда",
      "value": "Цезарь (45 шт, 450 000 тг)",
      "change": {
        "value": "+23%",
        "trend": "up"
      }
    }
  ]
}
```

### 2. Денежные потоки

**Endpoint:** `GET /reports/moneyflow`

```javascript
async function getMoneyFlowReports(date, period = 'day', organizationId = null) {
  try {
    const params = { date, period };
    if (organizationId) params.organization_id = organizationId;
    
    const response = await api.get('/reports/moneyflow', { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения денежных отчетов:', error);
    throw error;
  }
}

// Использование
const moneyFlow = await getMoneyFlowReports('15.01.2025', 'day');
```

**Ответ:**
```json
{
  "dishes": {
    "id": 1,
    "label": "Сумма всех проданных блюд по себестоимости",
    "value": "5 876 910 тг",
    "data": [
      {
        "id": 1,
        "name": "Цезарь",
        "amount": 135000,
        "quantity": 45
      }
    ]
  },
  "writeoffs": {
    "id": 2,
    "label": "Списания",
    "value": "50 000 тг",
    "data": [
      {
        "id": 1,
        "item": "Молоко",
        "quantity": 5,
        "reason": "Истек срок годности"
      }
    ]
  },
  "expenses": {
    "id": 3,
    "label": "Расходы",
    "value": "500 000 тг",
    "type": "negative",
    "data": [
      {
        "id": 1,
        "reason": "Аренда помещения",
        "amount": 500000,
        "date": "15.01.2025"
      }
    ]
  },
  "incomes": {
    "id": 4,
    "label": "Доходы",
    "value": "19 589 699 тг",
    "type": "positive",
    "data": [
      {
        "id": 1,
        "source": "Продажи",
        "amount": 19589699,
        "date": "15.01.2025"
      }
    ]
  }
}
```

---

## ⏰ Смены

### 1. Получить информацию о смене

**Endpoint:** `GET /shifts`

```javascript
async function getShifts(date = null, employeeId = null, organizationId = null) {
  try {
    const params = {};
    if (date) params.date = date;
    if (employeeId) params.employee_id = employeeId;
    if (organizationId) params.organization_id = organizationId;
    
    const response = await api.get('/shifts', { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения смены:', error);
    throw error;
  }
}

// Использование
const shift = await getShifts('15.01.2025');
```

**Ответ:**
```json
{
  "id": "shift-2025-01-15",
  "date": "15.01.2025",
  "startTime": "09:00",
  "endTime": null,
  "elapsedTime": "04:56:25",
  "openEmployees": 5,
  "totalAmount": 19589699,
  "finesCount": 0,
  "motivationCount": 3,
  "questsCount": 3,
  "status": "active"
}
```

**Пример компонента:**
```jsx
function ShiftInfo() {
  const [shift, setShift] = useState(null);

  useEffect(() => {
    const fetchShift = async () => {
      const data = await getShifts();
      setShift(data);
    };
    fetchShift();
    
    // Обновляем каждую минуту
    const interval = setInterval(fetchShift, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!shift) return <div>Загрузка...</div>;

  return (
    <div className="shift-info">
      <div className={`status ${shift.status}`}>
        {shift.status === 'active' ? '🟢 Смена активна' : '⚪ Смена завершена'}
      </div>
      
      <div className="time-info">
        <span>Начало: {shift.startTime}</span>
        {shift.endTime && <span>Окончание: {shift.endTime}</span>}
        <span>Прошло: {shift.elapsedTime}</span>
      </div>

      <div className="stats">
        <div>Сотрудников: {shift.openEmployees}</div>
        <div>Выручка: {shift.totalAmount.toLocaleString()} тг</div>
        <div>Квестов: {shift.questsCount}</div>
        {shift.finesCount > 0 && <div>Штрафов: {shift.finesCount}</div>}
      </div>
    </div>
  );
}
```

### 2. Статус смены официанта

**Endpoint:** `GET /waiter/{waiterId}/shift/status`

```javascript
async function getWaiterShiftStatus(waiterId, organizationId = null) {
  try {
    const params = organizationId ? { organization_id: organizationId } : {};
    const response = await api.get(`/waiter/${waiterId}/shift/status`, { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения статуса смены:', error);
    throw error;
  }
}

// Использование
const status = await getWaiterShiftStatus(1);
```

**Ответ:**
```json
{
  "isActive": true,
  "shiftId": "123",
  "startTime": "09:00",
  "elapsedTime": "04:56:25"
}
```

**Пример использования:**
```jsx
function WaiterShiftStatus({ waiterId }) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const fetchStatus = async () => {
      const data = await getWaiterShiftStatus(waiterId);
      setStatus(data);
    };
    fetchStatus();
    
    // Обновляем каждые 30 секунд
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [waiterId]);

  if (!status) return null;

  return (
    <div className="shift-status">
      {status.isActive ? (
        <>
          <span className="indicator active">🟢</span>
          <span>На смене: {status.elapsedTime}</span>
        </>
      ) : (
        <>
          <span className="indicator inactive">⚪</span>
          <span>Не на смене</span>
        </>
      )}
    </div>
  );
}
```

---

## 🏢 Помещения и Столы

### 1. Получить список помещений

**Endpoint:** `GET /rooms`

```javascript
async function getRooms(organizationId = null) {
  try {
    const params = organizationId ? { organization_id: organizationId } : {};
    const response = await api.get('/rooms', { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения помещений:', error);
    throw error;
  }
}

// Использование
const rooms = await getRooms();
```

**Ответ:**
```json
{
  "rooms": [
    {
      "id": "1",
      "name": "Общий зал",
      "capacity": 50,
      "tables": [
        {
          "id": "1",
          "number": "1",
          "roomId": "1",
          "roomName": "Общий зал",
          "capacity": 4,
          "status": "available",
          "currentOrderId": null,
          "assignedEmployeeId": null
        }
      ]
    },
    {
      "id": "2",
      "name": "VIP-залы",
      "capacity": 20,
      "tables": [...]
    }
  ]
}
```

**Пример компонента:**
```jsx
function RoomsList() {
  const [rooms, setRooms] = useState([]);

  useEffect(() => {
    getRooms().then(data => setRooms(data.rooms));
  }, []);

  return (
    <div className="rooms-list">
      {rooms.map(room => (
        <div key={room.id} className="room-card">
          <h3>{room.name}</h3>
          <p>Вместимость: {room.capacity} человек</p>
          <div className="tables-grid">
            {room.tables.map(table => (
              <div 
                key={table.id} 
                className={`table ${table.status}`}
              >
                <span>Стол {table.number}</span>
                <span className="capacity">{table.capacity} мест</span>
                {table.status === 'occupied' && (
                  <span className="occupied">Занят</span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

### 2. Получить список столов

**Endpoint:** `GET /tables`

```javascript
async function getTables(roomId = null, status = null, organizationId = null) {
  try {
    const params = {};
    if (roomId) params.room_id = roomId;
    if (status) params.status = status; // "available" | "occupied" | "disabled" | "all"
    if (organizationId) params.organization_id = organizationId;
    
    const response = await api.get('/tables', { params });
    return response.data;
  } catch (error) {
    console.error('Ошибка получения столов:', error);
    throw error;
  }
}

// Использование
const availableTables = await getTables(null, 'available');
```

**Ответ:**
```json
{
  "tables": [
    {
      "id": "1",
      "number": "1",
      "roomId": "1",
      "roomName": "Общий зал",
      "capacity": 4,
      "status": "available",
      "currentOrderId": null,
      "assignedEmployeeId": null
    }
  ]
}
```

---

## 👥 Сотрудники

### 1. Создать штраф

**Endpoint:** `POST /fines`

```javascript
async function createFine(fineData) {
  try {
    const response = await api.post('/fines', fineData);
    return response.data;
  } catch (error) {
    console.error('Ошибка создания штрафа:', error);
    throw error;
  }
}

// Использование
const fine = await createFine({
  employeeId: "1",
  employeeName: "Аслан Аманов",
  reason: "Опоздание на работу",
  amount: 5000,
  date: "15.01.2025"
});
```

**Ответ:**
```json
{
  "success": true,
  "message": "Fine created successfully",
  "fine_id": 123
}
```

**Пример формы:**
```jsx
function CreateFineForm({ employee, onSuccess }) {
  const [formData, setFormData] = useState({
    employeeId: employee.id,
    employeeName: employee.name,
    reason: '',
    amount: 0,
    date: new Date().toLocaleDateString('ru-RU'),
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await createFine(formData);
      alert('Штраф создан успешно!');
      onSuccess?.();
    } catch (error) {
      alert('Ошибка создания штрафа');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3>Создать штраф для {employee.name}</h3>
      
      <textarea
        placeholder="Причина штрафа"
        value={formData.reason}
        onChange={(e) => setFormData({...formData, reason: e.target.value})}
        required
      />
      
      <input
        type="number"
        placeholder="Сумма (тг)"
        value={formData.amount}
        onChange={(e) => setFormData({...formData, amount: Number(e.target.value)})}
        required
      />
      
      <button type="submit">Создать штраф</button>
    </form>
  );
}
```

### 2. Обновить время смены

**Endpoint:** `PUT /employees/{employeeId}/shift-time`

```javascript
async function updateShiftTime(employeeId, shiftTime) {
  try {
    const response = await api.put(`/employees/${employeeId}/shift-time`, {
      shiftTime // формат: "09:30"
    });
    return response.data;
  } catch (error) {
    console.error('Ошибка обновления времени смены:', error);
    throw error;
  }
}

// Использование
await updateShiftTime(1, "09:30");
```

**Ответ:**
```json
{
  "success": true,
  "message": "Shift time updated successfully"
}
```

---

## ⚠️ Обработка ошибок

### Общая структура ошибок

```javascript
// Настройка обработчика ошибок
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Сервер ответил с ошибкой
      const { status, data } = error.response;
      
      switch (status) {
        case 401:
          // Неавторизован - перенаправить на логин
          localStorage.removeItem('authToken');
          window.location.href = '/login';
          break;
        case 404:
          // Не найдено
          console.error('Ресурс не найден:', data.detail);
          break;
        case 500:
          // Ошибка сервера
          console.error('Ошибка сервера:', data.detail);
          break;
        default:
          console.error('Ошибка:', data.detail);
      }
    } else if (error.request) {
      // Запрос был отправлен, но ответа не получено
      console.error('Нет ответа от сервера');
    } else {
      // Ошибка при настройке запроса
      console.error('Ошибка запроса:', error.message);
    }
    
    return Promise.reject(error);
  }
);
```

### Типичные ошибки

```javascript
// 401 Unauthorized
{
  "detail": "Invalid or missing token"
}

// 404 Not Found
{
  "detail": "Employee not found"
}

// 500 Internal Server Error
{
  "detail": "Internal server error: ..."
}
```

### Пример обработки в компоненте

```jsx
function DataComponent() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const result = await getAnalytics();
        setData(result);
      } catch (err) {
        setError(err.response?.data?.detail || 'Произошла ошибка');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) return <div>Загрузка...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!data) return <div>Нет данных</div>;

  return <div>{/* Отображение данных */}</div>;
}
```

---

## 📝 Полезные утилиты

### Форматирование даты

```javascript
// Преобразование Date в формат DD.MM.YYYY
function formatDate(date) {
  const d = new Date(date);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}.${month}.${year}`;
}

// Использование
const today = formatDate(new Date()); // "15.01.2025"
```

### Форматирование суммы

```javascript
// Форматирование числа с разделителями
function formatCurrency(amount) {
  return `${amount.toLocaleString('ru-RU')} тг`;
}

// Использование
formatCurrency(1234567); // "1 234 567 тг"
```

### Парсинг времени

```javascript
// Преобразование "HH:mm:ss" в читаемый формат
function formatElapsedTime(time) {
  const [hours, minutes, seconds] = time.split(':');
  return `${hours}ч ${minutes}м`;
}

// Использование
formatElapsedTime("04:56:25"); // "04ч 56м"
```

---

## 🎨 Примеры стилей

### CSS для карточек

```css
.metric-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.metric-card .label {
  color: #666;
  font-size: 14px;
}

.metric-card h3 {
  font-size: 32px;
  margin: 10px 0;
  color: #333;
}

.metric-card .change {
  font-size: 14px;
  font-weight: 600;
}

.metric-card .change.up {
  color: #10b981;
}

.metric-card .change.down {
  color: #ef4444;
}

.quest-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.quest-card.completed {
  background: #f0fdf4;
  border-color: #10b981;
}

.progress-bar {
  height: 8px;
  background: #10b981;
  border-radius: 4px;
  transition: width 0.3s;
}
```

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
npm install axios
```

### 2. Создание API клиента

```javascript
// api/client.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8008',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
```

### 3. Создание сервисов

```javascript
// services/questsService.js
import api from '../api/client';

export const questsService = {
  getWaiterQuests: (waiterId, date, organizationId) => 
    api.get(`/waiter/${waiterId}/quests`, { 
      params: { date, organization_id: organizationId } 
    }),
  
  getQuestDetails: (questId, organizationId) =>
    api.get(`/quests/${questId}`, { 
      params: { organization_id: organizationId } 
    }),
  
  createQuest: (data) =>
    api.post('/quests', data),
};
```

### 4. Использование в компонентах

```javascript
import { questsService } from './services/questsService';

function MyComponent() {
  useEffect(() => {
    questsService.getWaiterQuests(1, '15.01.2025')
      .then(response => console.log(response.data))
      .catch(error => console.error(error));
  }, []);
}
```

---

## 📞 Поддержка

При возникновении проблем:
1. Проверьте, что сервер запущен
2. Проверьте токен авторизации
3. Проверьте формат параметров (даты, ID и т.д.)
4. Проверьте консоль браузера на наличие ошибок

**Документация API:** `http://localhost:8008/docs`

---

Удачной разработки! 🚀

