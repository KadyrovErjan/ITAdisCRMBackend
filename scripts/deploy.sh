#!/usr/bin/env bash
# Safe in-place production deployment. Run from GitHub Actions or manually.
set -Eeuo pipefail

REPOSITORY_DIR="${REPOSITORY_DIR:-/opt/itadiscrm}"
APP_DIR="$REPOSITORY_DIR/backend"

install_prerequisites() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Deployment must run as root so it can install/operate Docker and Nginx." >&2
    exit 1
  fi

  local packages_missing=0
  for command in curl git nginx certbot; do
    command -v "$command" > /dev/null || packages_missing=1
  done
  dpkg-query --show python3-certbot-nginx > /dev/null 2>&1 || packages_missing=1

  export DEBIAN_FRONTEND=noninteractive
  if [[ "$packages_missing" -eq 1 ]]; then
    apt-get update
    apt-get install -y ca-certificates curl git nginx certbot python3-certbot-nginx
  fi

  if ! command -v docker > /dev/null || ! docker compose version > /dev/null 2>&1; then
    apt-get update
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi

  systemctl enable --now docker nginx
}

install_nginx_site() {
  local source_file="$REPOSITORY_DIR/deploy/nginx/itadiscrm-api.conf"
  local available_file="/etc/nginx/sites-available/itadiscrm-api.conf"
  local enabled_file="/etc/nginx/sites-enabled/itadiscrm-api.conf"

  # Do not overwrite the file after Certbot has added its TLS configuration.
  if [[ ! -e "$available_file" ]]; then
    install -m 0644 "$source_file" "$available_file"
  fi
  if [[ ! -e "$enabled_file" ]]; then
    ln -s "$available_file" "$enabled_file"
  fi
  nginx -t
  systemctl reload nginx
}

failure_diagnostics() {
  status=$?
  echo "Deployment failed (exit $status). Recent container status and logs follow:" >&2
  if [[ -d "$APP_DIR" ]]; then
    docker compose --project-directory "$APP_DIR" ps >&2 || true
    docker compose --project-directory "$APP_DIR" logs --tail=100 web db >&2 || true
  fi
  exit "$status"
}
trap failure_diagnostics ERR

gunicorn_health_check() {
  local status_code
  status_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 3 --max-time 5 \
    --header 'Host: api.itadiscrm.com.kg' \
    --header 'X-Forwarded-Proto: https' \
    http://127.0.0.1:8000/healthz/ || true)"
  [[ "$status_code" == '200' ]]
}

backup_postgres() {
  local backup_dir="$REPOSITORY_DIR/backups"
  local timestamp backup_file checksum_file

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_file="$backup_dir/itadiscrm-postgres-${timestamp}.dump"
  checksum_file="${backup_file}.sha256"

  # This host directory is intentionally outside the web container and is not
  # part of the Git checkout's tracked application files.
  install -d -m 0700 "$backup_dir"
  umask 077

  echo "Creating PostgreSQL backup: $backup_file"
  docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_file"
  [[ -s "$backup_file" ]] || { echo "PostgreSQL backup is empty; deployment stopped." >&2; exit 1; }

  sha256sum "$backup_file" > "$checksum_file"
  docker compose exec -T db pg_restore --list < "$backup_file" > /dev/null
  echo "PostgreSQL backup verified: $backup_file ($(cut -d ' ' -f 1 "$checksum_file"))"
}

[[ -d "$REPOSITORY_DIR/.git" ]] || { echo "Missing Git checkout at $REPOSITORY_DIR; complete the documented initial clone first." >&2; exit 1; }
install_prerequisites
[[ -f "$APP_DIR/.env" ]] || { echo "Missing $APP_DIR/.env; deployment stopped." >&2; exit 1; }

cd "$REPOSITORY_DIR"
git fetch --prune origin main
git checkout --detach origin/main

cd "$APP_DIR"
install_nginx_site
docker compose config --quiet
docker compose up -d db
backup_postgres
docker compose build web

# Run schema/static changes with the newly built image before replacing web.
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d --no-deps web

for attempt in {1..15}; do
  if gunicorn_health_check; then
    docker compose ps
    echo "Deployment succeeded."
    exit 0
  fi
  sleep 2
done

echo "Health check did not become ready." >&2
exit 1
