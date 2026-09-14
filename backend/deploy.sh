#!/usr/bin/env bash
#
# ITAdis CRM - Quick Deploy Script
# Запуск: bash deploy.sh
#

set -e

echo "🚀 ITAdis CRM - Deployment Started"
echo "===================================="

# 1. Pull latest changes
echo "📥 Pulling latest code..."
git pull origin main

# 2. Stop containers
echo "🛑 Stopping containers..."
sudo docker compose down

# 3. Build and start
echo "🔨 Building and starting containers..."
sudo docker compose up -d --build

# 4. Wait for DB
echo "⏳ Waiting for database..."
sleep 10

# 5. Run migrations
echo "📊 Running migrations..."
sudo docker compose exec -T web python manage.py migrate --noinput

# 6. Collect static
echo "📦 Collecting static files..."
sudo docker compose exec -T web python manage.py collectstatic --noinput

# 7. Check status
echo "✅ Checking container status..."
sudo docker compose ps

echo ""
echo "===================================="
echo "✅ Deployment completed!"
echo "===================================="
echo ""
echo "📝 Useful commands:"
echo "  sudo docker compose logs -f web    # View logs"
echo "  sudo docker compose ps             # Check status"
echo "  sudo docker compose restart        # Restart"
echo ""
echo "🌐 URLs:"
echo "  http://13.62.102.119:8000/admin/"
echo "  https://api.itadiscrm.com.kg/admin/"
