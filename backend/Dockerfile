# Используем официальный Python образ
FROM python:3.12-slim

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Создаём рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY ../requirements.txt /app/

# Устанавливаем Python зависимости
RUN pip install --upgrade pip && \
    pip install gunicorn && \
    pip install -r requirements.txt

# Копируем проект
COPY . /app/

# Создаём директории для static и media
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Устанавливаем права
RUN chmod +x /app/manage.py

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/admin/login/ || exit 1

# Команда по умолчанию
CMD ["gunicorn", "mysite.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
