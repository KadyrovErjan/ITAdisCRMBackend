# Deploying the API on Hetzner

This guide deploys only `api.itadiscrm.com.kg` to `2.29.61.103`. Do not change the `itadiscrm.com.kg` or `www` records: they remain Vercel frontend records.

## 1. Prepare the Ubuntu 24.04 server

Log in as `root`, update the server, install Docker/Nginx/Git, and enable only SSH, HTTP, and HTTPS in the firewall:

```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl git nginx ufw
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker nginx
docker compose version
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
```

Do **not** allow ports `5432` or `8000`. Compose binds port 8000 to `127.0.0.1` only, and PostgreSQL has no host port.

## 2. Clone and configure the application

First create a **server-to-GitHub read-only deploy key** on Hetzner. Add the
printed public key in GitHub **Settings → Deploy keys** with read-only access;
the private key stays on the server. Then clone using the SSH URL and make the
deployment script executable:

```bash
mkdir -p -m 700 /root/.ssh
ssh-keygen -t ed25519 -C "itadiscrm-hetzner-read" -f /root/.ssh/itadiscrm_github -N ""
cat /root/.ssh/itadiscrm_github.pub
printf 'Host github.com\n  IdentityFile /root/.ssh/itadiscrm_github\n  IdentitiesOnly yes\n' >> /root/.ssh/config
chmod 600 /root/.ssh/config
ssh-keyscan github.com >> /root/.ssh/known_hosts
git clone git@github.com:YOUR_GITHUB_OWNER/ITAdisCRMBackend.git /opt/itadiscrm
chmod 700 /opt/itadiscrm/scripts/deploy.sh
cp /opt/itadiscrm/backend/.env.production.example /opt/itadiscrm/backend/.env
chmod 600 /opt/itadiscrm/backend/.env
nano /opt/itadiscrm/backend/.env
```

Set unique values for `SECRET_KEY` and `DB_PASSWORD`; do not leave the example
placeholders. Hex values avoid special-character interpolation in Docker's
`.env` parser:

```bash
openssl rand -hex 50  # SECRET_KEY
openssl rand -hex 32  # DB_PASSWORD
```

Keep `.env` only on the server. The deployment script refuses to run without it and never writes it.

## 3. Configure Cloudflare DNS

In Cloudflare DNS, create or edit exactly this record:

| Type | Name | Content | Proxy |
| --- | --- | --- | --- |
| A | `api` | `2.29.61.103` | Proxied (orange cloud) |

Leave the existing root and `www` CNAME/Vercel records unchanged. Wait until
`api.itadiscrm.com.kg` resolves to `2.29.61.103`. The first deployment creates
an HTTP-only Nginx site; issue the certificate in the next step.

## 4. First deployment, HTTPS, and verification

Run the same script used by CI. It installs missing Docker, Docker Compose
plugin, Nginx, Certbot, its Nginx plugin, and Git; then builds the containers.

```bash
/opt/itadiscrm/scripts/deploy.sh
curl -fsS http://127.0.0.1:8000/healthz/
docker compose --project-directory /opt/itadiscrm/backend ps
```

Request the Let's Encrypt certificate. If Cloudflare interferes with the HTTP-01
challenge, temporarily set **only** the `api` record to **DNS only** (grey
cloud), run Certbot, and turn the `api` proxy back on after issuance:

```bash
certbot --nginx -d api.itadiscrm.com.kg --redirect --agree-tos -m YOUR_REAL_EMAIL --no-eff-email
systemctl status certbot.timer
```

Certbot stores its private key and automatic-renewal configuration on the
server. Do not commit them. It also adds the HTTPS Nginx block; later deploys
preserve that server-side file rather than overwriting it.

After Certbot succeeds, set **SSL/TLS → Overview** in Cloudflare to **Full
(strict)**, never Flexible, and verify:

```bash
curl -fsS https://api.itadiscrm.com.kg/healthz/
```

The expected health response is `{"status": "ok"}`. To create the initial owner only after a successful deployment:

```bash
docker compose --project-directory /opt/itadiscrm/backend exec web python manage.py init_owner
```

## 5. Enable GitHub Actions deployment

Create a separate **GitHub-Actions-to-server** SSH key locally. Add its public
half to `/root/.ssh/authorized_keys` on Hetzner. This is not the server's
GitHub read key from step 2:

```bash
ssh-keygen -t ed25519 -C "itadiscrm-github-actions" -f ~/.ssh/itadiscrm_deploy
cat ~/.ssh/itadiscrm_deploy.pub
# Paste the public key into /root/.ssh/authorized_keys on Hetzner.
```

In GitHub repository **Settings → Secrets and variables → Actions**, create:

| Secret | Value |
| --- | --- |
| `HETZNER_HOST` | `2.29.61.103` |
| `HETZNER_USER` | `root` |
| `HETZNER_SSH_KEY` | contents of the private `itadiscrm_deploy` key |
| `HETZNER_SSH_PORT` | `22` (optional) |

Never add the deploy-key private key, `.env`, database password, or Django secret to Git.

Each push to `main` opens one serialized deployment: GitHub connects by SSH, fetches `origin/main`, builds the web image, runs migrations and `collectstatic`, restarts only the web container, and verifies `http://127.0.0.1:8000/healthz/`. Failed deployments print the last container logs but not the `.env` contents.

## Operations, backup, and recovery

Before any destructive maintenance, create a database backup:

```bash
mkdir -p /opt/itadiscrm/backups
docker compose --project-directory /opt/itadiscrm/backend exec -T db pg_dump -U "$(grep '^DB_USER=' /opt/itadiscrm/backend/.env | cut -d= -f2-)" "$(grep '^DB_NAME=' /opt/itadiscrm/backend/.env | cut -d= -f2-)" > /opt/itadiscrm/backups/itadiscrm-$(date +%F-%H%M%S).sql
```

Diagnostics:

```bash
docker compose --project-directory /opt/itadiscrm/backend ps
docker compose --project-directory /opt/itadiscrm/backend logs --tail=200 web db
tail -n 200 /var/log/nginx/itadiscrm-api.error.log
nginx -t
```

To roll back application code, identify the prior good commit and deliberately deploy it (this does not roll back database migrations):

```bash
cd /opt/itadiscrm
git fetch --all --tags
git checkout <known-good-commit>
cd backend && docker compose build web && docker compose up -d --no-deps web
curl -f http://127.0.0.1:8000/healthz/
```

Never use `docker compose down -v` on this server: it destroys named database volumes.
