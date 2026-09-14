# 🔧 Quick Fix - Исправление ошибок

## Проблемы:
1. ❌ Pillow не установлен (ImageField требует Pillow)
2. ❌ .env файл не создан

## Решение:

```bash
# 1. Удалить старые контейнеры
sudo docker compose down -v

# 2. Обновить код (с исправленным requirements.txt)
git pull origin main

# 3. Создать .env файл
cp .env.example .env
nano .env
```

**Минимальное содержимое `.env`:**
```env
SECRET_KEY=django-insecure-temp-key-change-later
DEBUG=False
ALLOWED_HOSTS=13.62.102.119,api.itadiscrm.com.kg

DB_NAME=itadis_db
DB_USER=itadis_user
DB_PASSWORD=secure_password_123
DB_HOST=db
DB_PORT=5432

CORS_ALLOWED_ORIGINS=https://api.itadiscrm.com.kg
```

```bash
# 4. Пересобрать и запустить
sudo docker compose build --no-cache
sudo docker compose up -d

# 5. Проверить логи
sudo docker compose logs -f

# 6. Когда контейнеры запустятся, выполнить миграции
sudo docker compose exec web python manage.py migrate

# 7. Создать суперпользователя
sudo docker compose exec web python manage.py createsuperuser

# 8. Собрать статику
sudo docker compose exec web python manage.py collectstatic --noinput

# 9. Проверить статус
sudo docker compose ps
```

## Проверка:
```bash
# Должны быть запущены оба контейнера
sudo docker compose ps
# STATUS должен быть "Up"

# Проверить backend
curl http://localhost:8000/admin/
```

Если все ОК, продолжайте с Nginx настройкой!
