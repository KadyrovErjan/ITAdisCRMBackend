# 🎓 ITAdis CRM - Backend API

> Django REST API для системы управления учебным центром

[![Django](https://img.shields.io/badge/Django-5.1.4-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)

---

## 🚀 Production Deployment (AWS + Docker)

**Домен**: https://api.itadiscrm.com.kg  
**IP**: 13.62.102.119

### Быстрый старт:

```bash
# 1. Подключиться к AWS EC2
ssh -i "your-key.pem" ubuntu@13.62.102.119

# 2. Клонировать проект
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/your-username/ITAdisCRMBackend.git
cd ITAdisCRMBackend/backend

# 3. Настроить .env
cp .env.production.example .env
nano .env  # Заполнить SECRET_KEY и DB_PASSWORD

# 4. Запустить Docker
sudo docker compose up -d

# 5. Первый запуск
sudo docker compose exec web python manage.py migrate
sudo docker compose exec web python manage.py createsuperuser
sudo docker compose exec web python manage.py collectstatic --noinput

# 6. Настроить Nginx
sudo apt install nginx certbot python3-certbot-nginx -y
sudo cp nginx.conf /etc/nginx/sites-available/itadiscrm
sudo ln -s /etc/nginx/sites-available/itadiscrm /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# 7. Получить SSL (после настройки DNS)
sudo certbot --nginx -d api.itadiscrm.com.kg
```

**📚 Подробная инструкция**: [PRODUCTION_DEPLOY.md](./backend/PRODUCTION_DEPLOY.md)

---

## 💻 Локальная разработка

### Требования
- Python 3.12+
- PostgreSQL 15+ (или Docker)

### Установка

```bash
# 1. Клонировать
git clone https://github.com/your-username/ITAdisCRMBackend.git
cd ITAdisCRMBackend/backend

# 2. Виртуальное окружение
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Зависимости
pip install -r requirements.txt

# 4. Настроить .env
cp .env.example .env
# Отредактировать .env

# 5. Миграции
python manage.py migrate

# 6. Создать суперпользователя
python manage.py createsuperuser

# 7. Запустить сервер
python manage.py runserver
```

### С Docker (локально)

```bash
cd backend

# Запустить
docker compose up -d

# Миграции
docker compose exec web python manage.py migrate

# Создать суперпользователя
docker compose exec web python manage.py createsuperuser

# Просмотр логов
docker compose logs -f
```

---

## 📋 API Endpoints

### Authentication
- `POST /api/v1/auth/login/` - Вход
- `POST /api/v1/auth/logout/` - Выход
- `POST /api/v1/auth/token/refresh/` - Обновление токена
- `GET /api/v1/auth/me/` - Текущий пользователь

### Users
- `GET /api/v1/users/` - Список пользователей
- `POST /api/v1/users/` - Создать пользователя
- `GET /api/v1/users/{id}/` - Детали пользователя

### Students
- `GET /api/v1/students/` - Список студентов
- `POST /api/v1/students/` - Создать студента

### Groups
- `GET /api/v1/groups/` - Список групп
- `POST /api/v1/groups/` - Создать группу

**Swagger UI**: https://api.itadiscrm.com.kg/api/schema/swagger-ui/  
**API Cheatsheet**: [API_CHEATSHEET.md](./API_CHEATSHEET.md)

---

## 🔐 Безопасность

- ✅ JWT Authentication
- ✅ HTTPS/SSL
- ✅ CORS настроен
- ✅ Rate limiting
- ✅ Argon2 password hashing
- ✅ SQL injection защита

---

## 🛠️ Полезные команды

### Docker

```bash
# Логи
sudo docker compose logs -f web

# Перезапуск
sudo docker compose restart

# Остановка
sudo docker compose down

# Миграции
sudo docker compose exec web python manage.py migrate

# Shell
sudo docker compose exec web python manage.py shell
```

### Обновление

```bash
# Быстрое обновление
bash deploy.sh

# Или вручную
git pull
sudo docker compose down
sudo docker compose up -d --build
sudo docker compose exec web python manage.py migrate
sudo docker compose exec web python manage.py collectstatic --noinput
```

---

## 📊 Мониторинг

```bash
# Статус контейнеров
sudo docker compose ps

# Использование ресурсов
sudo docker stats

# Nginx логи
sudo tail -f /var/log/nginx/itadiscrm-error.log

# Django логи
sudo docker compose logs -f web
```

---

## 🌐 Production URLs

- **Backend API**: https://api.itadiscrm.com.kg/api/v1/
- **Admin Panel**: https://api.itadiscrm.com.kg/admin/
- **Swagger**: https://api.itadiscrm.com.kg/api/schema/swagger-ui/
- **ReDoc**: https://api.itadiscrm.com.kg/api/schema/redoc/

---

## 📞 Поддержка

- **Issues**: GitHub Issues
- **Documentation**: См. `PRODUCTION_DEPLOY.md`

---

**Разработано для ITAdis Education Center** ❤️
