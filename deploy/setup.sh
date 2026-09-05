#!/usr/bin/env bash
# Provision the FinancialAnalyst single-server deployment on an Ubuntu
# VM (target: Azure for Students B2ats_v2, Ubuntu 24.04 LTS).
#
# Run as root FROM the repo directory on the VM. The repo must already be
# cloned there (e.g. /opt/financial-analyst) with a .env file present.
#
#   DOMAIN=your-public-hostname ./deploy/setup.sh
#
# DOMAIN is the public hostname the site is served on, e.g.
# "mydomain.me" or "myvm.eastus.cloudapp.azure.com". The Caddy web server
# obtains a Let's Encrypt certificate for it automatically. APP_DIR (the
# repo's location on the VM, default /opt/financial-analyst) may also be
# overridden; the Caddyfile and systemd units are rendered to match.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/financial-analyst}"
APP_USER="${APP_USER:-financial-analyst}"
REQUIREMENTS="${REQUIREMENTS:-$APP_DIR/deploy/requirements-server.txt}"
DOMAIN="${DOMAIN:?Set DOMAIN to the public hostname the site is served on}"

# sed-replace the {{APP_DIR}} placeholder shared by the Caddyfile and the
# systemd units, so a non-default APP_DIR installs consistently.
esc=$(printf '%s' "$APP_DIR" | sed 's/[\/&]/\\&/g')

if [[ ! -d "$APP_DIR" ]]; then
    echo "repo not found at $APP_DIR; clone it first" >&2
    exit 1
fi
cd "$APP_DIR"

if [[ ! -f "$APP_DIR/.env" ]]; then
    echo "missing $APP_DIR/.env (copy deploy/.env.example and fill secrets)" >&2
    exit 1
fi

echo "==> installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl python3-venv python3-pip nodejs npm

echo "==> installing Caddy (official apt repo)"
if ! command -v caddy >/dev/null 2>&1; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    apt-get update -y
    apt-get install -y caddy
fi

echo "==> creating app user"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "$APP_DIR" "$APP_USER"
fi

echo "==> python venv and server requirements"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r "$REQUIREMENTS"

echo "==> building the frontend"
npm --prefix web ci
npm --prefix web run build

echo "==> writing config and service units"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"
sed "s/DOMAIN/$DOMAIN/g; s/{{APP_DIR}}/$esc/g" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
for unit in "$APP_DIR"/deploy/systemd/*.service; do
    sed "s/{{APP_DIR}}/$esc/g" "$unit" > "/etc/systemd/system/$(basename "$unit")"
done

echo "==> starting services"
systemctl daemon-reload
systemctl enable --now caddy financial-analyst-api financial-analyst-worker
systemctl restart caddy financial-analyst-api financial-analyst-worker

echo "==> done. Verify with:"
echo "    curl -fsS https://$DOMAIN/health"
echo "    systemctl status financial-analyst-api financial-analyst-worker"
