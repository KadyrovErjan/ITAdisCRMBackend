# 📋 API Шпаргалка для ITadis CRM

## 🔐 Аутентификация

### 1. Вход в систему
```bash
POST /api/v1/auth/login/
Content-Type: application/json

{
  "login": "director",
  "password": "director2025"
}
```

**Ответ:**
```json
{
  "access": "eyJhbGci...",
  "refresh": "eyJhbGci...",
  "user": {
    "id": "uuid",
    "login": "director",
    "full_name": "Директор ITadis",
    "role": "director"
  }
}
```

### 2. Использование токена
Все запросы требуют заголовок:
```
Authorization: Bearer <access_token>
```

### 3. Обновление токена
```bash
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGci..."
}
```

---

## 👥 Управление пользователями

### Получить список всех работников (только директор)
```bash
GET /api/v1/users/
Authorization: Bearer <access_token>
```

### Создать нового работника (только директор)
```bash
POST /api/v1/users/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "login": "kassir1",
  "password": "secure_password123",
  "full_name": "Айгуль Иванова",
  "role": "cashier",
  "is_active": true
}
```

**Роли:**
- `cashier` - Кассир
- `accountant` - Бухгалтер  
- `director` - Директор

### Получить свой профиль (все роли)
```bash
GET /api/v1/users/me/
Authorization: Bearer <access_token>
```

### Обновить свой профиль (все роли)
```bash
PATCH /api/v1/users/me/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "full_name": "Новое Имя"
}
```

### Сменить свой пароль (все роли)
```bash
PATCH /api/v1/users/me/change-password/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "old_password": "старый_пароль",
  "new_password": "новый_пароль"
}
```

---

## 📚 Группы

### Получить список групп
```bash
GET /api/v1/groups/
Authorization: Bearer <access_token>

# С фильтрацией по статусу
GET /api/v1/groups/?status=active
```

**Статусы групп:**
- `active` - Активдүү (Активная)
- `completed` - Аяктады (Завершена)
- `archived` - Архивделген (Архивная)

### Создать группу (кассир)
```bash
POST /api/v1/groups/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "Python Начинающие",
  "subject": "Python Programming",
  "schedule": "Пн, Ср, Пт 18:00-20:00",
  "total_lessons": 24,
  "current_lesson": 0
}
```

### Получить студентов группы
```bash
GET /api/v1/groups/{group_id}/students/
Authorization: Bearer <access_token>
```

### Изменить статус группы
```bash
PATCH /api/v1/groups/{group_id}/change-status/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "status": "completed"
}
```

---

## 👨‍🎓 Студенты

### Получить список студентов
```bash
GET /api/v1/students/
Authorization: Bearer <access_token>

# С фильтрацией
GET /api/v1/students/?status=active
GET /api/v1/students/?group={group_id}
```

**Статусы студентов:**
- `active` - Толук төлөп бүттү (Оплатил полностью)
- `debt` - Төлөө элек (Есть долг)
- `frozen` - Тоңдурулган (Заморожен)
- `expelled` - Чыгарылган (Отчислен)

### Зарегистрировать студента (кассир)
```bash
POST /api/v1/students/register/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "full_name": "Нурбек Асанов",
  "group_id": "uuid-группы",
  "initial_payment": "5000.00"
}
```

### Принять платеж от студента (кассир)
```bash
POST /api/v1/students/{student_id}/payments/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": "2000.00"
}
```

### Изменить статус студента (кассир - свой, директор - любой)
```bash
PATCH /api/v1/students/{student_id}/change_status/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "status": "frozen"
}
```

### Перевести студента в другую группу (кассир - свой, директор - любой)
```bash
POST /api/v1/students/{student_id}/transfer/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "new_group_id": "uuid-новой-группы"
}
```

---

## 💰 Финансы

### Получить свой баланс (все роли)
```bash
GET /api/v1/balances/me/
Authorization: Bearer <access_token>
```

### Получить балансы всех (бухгалтер, директор)
```bash
GET /api/v1/balances/
Authorization: Bearer <access_token>
```

### Создать сбор денег (бухгалтер, директор)
```bash
POST /api/v1/collections/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "from_user_id": "uuid-кассира",
  "amount": "10000.00"
}
```

### Создать расход (бухгалтер, директор)
```bash
POST /api/v1/expenses/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": "3000.00",
  "comment": "Оплата за интернет"
}
```

---

## 📊 Аналитика (только директор)

### Общая сводка
```bash
GET /api/v1/analytics/summary/
Authorization: Bearer <access_token>

# За определенный период
GET /api/v1/analytics/summary/?start_date=2026-01-01&end_date=2026-12-31
```

**Ответ:**
```json
{
  "total_income": "150000.00",
  "total_expenses": "45000.00",
  "net_profit": "105000.00",
  "active_students_count": 45,
  "active_groups_count": 8,
  "period": {
    "start": "2026-01-01",
    "end": "2026-12-31"
  }
}
```

### Помесячная аналитика
```bash
GET /api/v1/analytics/monthly/
Authorization: Bearer <access_token>

# За конкретный год
GET /api/v1/analytics/monthly/?year=2026
```

### Аналитика по кассирам
```bash
GET /api/v1/analytics/cashiers/
Authorization: Bearer <access_token>
```

### Аналитика по группам
```bash
GET /api/v1/analytics/groups/
Authorization: Bearer <access_token>
```

---

## 📝 Транзакции

### Получить список транзакций
```bash
GET /api/v1/transactions/
Authorization: Bearer <access_token>

# Кассир видит только свои транзакции
# Бухгалтер/директор видят все
```

### Получить конкретную транзакцию
```bash
GET /api/v1/transactions/{transaction_id}/
Authorization: Bearer <access_token>
```

---

## 🔍 Журнал аудита (директор)

### Получить логи
```bash
GET /api/v1/audit-log/
Authorization: Bearer <access_token>

# С фильтрацией
GET /api/v1/audit-log/?action=user.create
GET /api/v1/audit-log/?user={user_id}
GET /api/v1/audit-log/?object_type=Student
```

---

## 📄 Экспорт данных

### Экспорт аналитики в Excel (директор)
```bash
GET /api/v1/analytics/export/?start_date=2026-01-01&end_date=2026-12-31
Authorization: Bearer <access_token>
```

---

## 🛠️ PowerShell примеры

### Вход и сохранение токена
```powershell
$login = @{
    login = 'director'
    password = 'director2025'
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/auth/login/' -Method Post -Body $login -ContentType 'application/json'
$token = $response.access
```

### Использование токена
```powershell
$headers = @{
    'Authorization' = "Bearer $token"
}

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/users/me/' -Headers $headers
```

### Создание работника
```powershell
$newUser = @{
    login = 'kassir1'
    password = 'password123'
    full_name = 'Айгуль Иванова'
    role = 'cashier'
    is_active = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/users/' -Method Post -Headers $headers -Body $newUser -ContentType 'application/json'
```

---

## ⚡ Быстрые команды для тестирования

### 1. Войти как директор
```powershell
$body = @{login='director'; password='director2025'} | ConvertTo-Json
$r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/auth/login/' -Method Post -Body $body -ContentType 'application/json'
$token = $r.access
$headers = @{'Authorization' = "Bearer $token"}
```

### 2. Получить свой профиль
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/users/me/' -Headers $headers
```

### 3. Создать кассира
```powershell
$newUser = @{login='kassir1'; password='kassir123'; full_name='Кассир Первый'; role='cashier'; is_active=$true} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/users/' -Method Post -Headers $headers -Body $newUser -ContentType 'application/json'
```

### 4. Получить список всех работников
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/users/' -Headers $headers
```

---

## 📚 Документация API

- **Swagger UI:** http://127.0.0.1:8000/api/schema/swagger-ui/
- **ReDoc:** http://127.0.0.1:8000/api/schema/redoc/
- **OpenAPI Schema:** http://127.0.0.1:8000/api/schema/

---

## 💡 Полезные ссылки

- **Backend:** http://127.0.0.1:8000
- **Admin Panel:** http://127.0.0.1:8000/admin
- **API Base:** http://127.0.0.1:8000/api/v1/

---

**Разработано для ITadis © 2026**
