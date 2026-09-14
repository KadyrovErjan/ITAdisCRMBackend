# 🚀 ITAdis CRM - Production Deployment

## Быстрый деплой на AWS с Docker

**Домен**: itadiscrm.com.kg  
**Backend API**: api.itadiscrm.com.kg  
**IP**: 13.62.102.119

---

## 1️⃣ Подготовка на AWS EC2

### Подключение к серверу
```bash
ssh -i "your-key.pem" ubuntu@13.62.102.119
```

### Установка Docker (✅ Уже сделано)
```bash
# Проверка
docker --version
docker compose version
```

---

## 2️⃣ Клонирование проекта

```bash
# Создать директорию
mkdir -p ~/apps && cd ~/apps

# Клонировать репозиторий
git clone https://github.com/your-username/ITAdisCRMBackend.git
cd ITAdisCRMBackend/backend
```

---

## 3️⃣ Настройка .env для Production

```bash
# Создать .env файл
nano .env
```

**Содержимое `.env`:**
```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=13.62.102.119,api.itadiscrm.com.kg,itadiscrm.com.kg

# Database (PostgreSQL в Docker)
DB_NAME=itadis_db
DB_USER=itadis_user
DB_PASSWORD=secure_password_here
DB_HOST=db
DB_PORT=5432

# CORS
CORS_ALLOWED_ORIGINS=https://api.itadiscrm.com.kg,https://itadiscrm.com.kg
```

**Генерация SECRET_KEY:**
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 4️⃣ Запуск с Docker Compose

```bash
# Запустить контейнеры
sudo docker compose up -d

# Проверить статус
sudo docker compose ps

# Посмотреть логи
sudo docker compose logs -f
```

### Первый запуск - миграции и супер юзер

```bash
# Выполнить миграции
sudo docker compose exec web python manage.py migrate

# Создать суперпользователя
sudo docker compose exec web python manage.py createsuperuser

# Собрать статику
sudo docker compose exec web python manage.py collectstatic --noinput
```

---

## 5️⃣ Проверка работы

```bash
# Проверить backend
curl http://localhost:8000/admin/

# Или в браузере
http://13.62.102.119:8000/admin/
```

---

## 6️⃣ Настройка Nginx + SSL

### Установка Nginx
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Конфигурация Nginx
```bash
sudo nano /etc/nginx/sites-available/itadiscrm
```

**Содержимое:**
```nginx
server {
    listen 80;
    server_name api.itadiscrm.com.kg itadiscrm.com.kg 13.62.102.119;
    
    client_max_body_size 10M;
    
    location /static/ {
        alias /home/ubuntu/apps/ITAdisCRMBackend/backend/staticfiles/;
    }
    
    location /media/ {
        alias /home/ubuntu/apps/ITAdisCRMBackend/backend/media/;
    }
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Активация
```bash
sudo ln -s /etc/nginx/sites-available/itadiscrm /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

---

## 7️⃣ SSL сертификат (Let's Encrypt)

**⚠️ Сначала настройте DNS в Cloudflare!**

```bash
# Получить сертификат
sudo certbot --nginx -d api.itadiscrm.com.kg -d itadiscrm.com.kg

# Выбрать:
# 1. Email
# 2. Agree to terms
# 3. Redirect HTTP to HTTPS (рекомендуется)
```

---

## 8️⃣ Cloudflare DNS Setup

### В Cloudflare Dashboard:

1. **DNS Records** → Add Record:
   - Type: `A`
   - Name: `api`
   - Content: `13.62.102.119`
   - Proxy: ✅ Proxied (оранжевое облако)

2. **DNS Records** → Add Record:
   - Type: `A`
   - Name: `@`
   - Content: `13.62.102.119`
   - Proxy: ✅ Proxied

3. **SSL/TLS** → Mode: **Full (strict)**

4. **DNS** → Изменить NS записи у регистратора домена

---

## 9️⃣ Обновление приложения

```bash
cd ~/apps/ITAdisCRMBackend/backend

# Получить изменения
git pull

# Пересобрать и перезапустить
sudo docker compose down
sudo docker compose up -d --build

# Миграции
sudo docker compose exec web python manage.py migrate

# Статика
sudo docker compose exec web python manage.py collectstatic --noinput
```

---

## 🔟 Полезные команды

```bash
# Просмотр логов
sudo docker compose logs -f web
sudo docker compose logs -f db

# Статус контейнеров
sudo docker compose ps

# Остановка
sudo docker compose down

# Перезапуск
sudo docker compose restart

# Вход в контейнер
sudo docker compose exec web bash
sudo docker compose exec web python manage.py shell

# Nginx логи
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

---

## ✅ Финальная проверка

После всех шагов проверьте:

- ✅ http://13.62.102.119 - работает
- ✅ https://api.itadiscrm.com.kg/admin/ - работает
- ✅ https://api.itadiscrm.com.kg/api/v1/ - работает
- ✅ SSL сертификат валиден

---

## 🐛 Troubleshooting

### Контейнеры не запускаются
```bash
sudo docker compose logs web
sudo docker compose logs db
```

### 502 Bad Gateway
```bash
# Проверить backend
curl http://localhost:8000

# Перезапустить
sudo docker compose restart
sudo systemctl restart nginx
```

### База данных не подключается
```bash
# Проверить контейнер БД
sudo docker compose ps db

# Логи БД
sudo docker compose logs db
```

---

**Готово! Backend на production! 🎉**
