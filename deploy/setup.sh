#!/usr/bin/env bash
# deploy/setup.sh — One-time server setup for DeckStudio
# Run as root on the target server.
# Usage: sudo bash deploy/setup.sh
set -euo pipefail

DOMAIN="deckstudio.karlekar.cloud"
APP_USER="deckstudio"
APP_DIR="/opt/deckstudio"
STATIC_DIR="/var/www/deckstudio"
PYTHON_MIN="3.11"

echo "==> DeckStudio server setup — $(date)"

# ── 1. System packages ───────────────────────────────────────────────────────
echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    nginx certbot python3-certbot-nginx \
    git curl

# ── 2. Service user ──────────────────────────────────────────────────────────
echo "==> Creating service user '${APP_USER}'..."
if ! id "${APP_USER}" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "${APP_DIR}" "${APP_USER}"
    echo "    Created."
else
    echo "    Already exists — skipping."
fi

# ── 3. Directory structure ───────────────────────────────────────────────────
echo "==> Creating directory structure..."
mkdir -p "${APP_DIR}/backend"
mkdir -p "${APP_DIR}/data/sessions"
mkdir -p "${APP_DIR}/data/exports"
mkdir -p "${APP_DIR}/venv"
mkdir -p "${STATIC_DIR}"

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
chown -R www-data:www-data "${STATIC_DIR}"
chmod 755 "${STATIC_DIR}"

# ── 4. Python venv ───────────────────────────────────────────────────────────
echo "==> Creating Python virtual environment..."
python3 -m venv "${APP_DIR}/venv"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}/venv"

# ── 5. nginx vhost ───────────────────────────────────────────────────────────
echo "==> Installing nginx vhost..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "${SCRIPT_DIR}/deckstudio.nginx" /etc/nginx/sites-available/deckstudio

# Enable (idempotent)
ln -sf /etc/nginx/sites-available/deckstudio /etc/nginx/sites-enabled/deckstudio

# Remove default if present
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl reload nginx
echo "    nginx vhost installed and reloaded."

# ── 6. systemd service ───────────────────────────────────────────────────────
echo "==> Installing systemd service..."
cp "${SCRIPT_DIR}/deckstudio.service" /etc/systemd/system/deckstudio.service
systemd-analyze verify /etc/systemd/system/deckstudio.service || true
systemctl daemon-reload
systemctl enable deckstudio
echo "    Service installed and enabled (not started yet — deploy backend first)."

# ── 7. SSL via certbot ───────────────────────────────────────────────────────
echo ""
echo "==> SSL setup:"
echo "    Run the following AFTER DNS is pointing to this server:"
echo ""
echo "    certbot --nginx -d ${DOMAIN}"
echo ""

echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Copy backend code:  rsync -av backend/ ${APP_DIR}/backend/"
echo "  2. Create .env file:   cp backend/.env.example ${APP_DIR}/backend/.env && nano ${APP_DIR}/backend/.env"
echo "  3. Install deps:       sudo -u ${APP_USER} ${APP_DIR}/venv/bin/pip install -r ${APP_DIR}/backend/requirements.txt"
echo "  4. Build frontend:     cd frontend && npm ci && npm run build && cp -r dist/* ${STATIC_DIR}/"
echo "  5. Start service:      systemctl start deckstudio"
echo "  6. SSL cert:           certbot --nginx -d ${DOMAIN}"
echo "  7. Check logs:         journalctl -u deckstudio -f"
