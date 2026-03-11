#!/usr/bin/env bash
# Run once as root: sudo bash /home/openclaw/.openclaw/workspace/projects/deckstudio/deploy/root_setup.sh
set -euo pipefail

REPO="/home/openclaw/.openclaw/workspace/projects/deckstudio"

echo "==> Creating /var/www/deckstudio..."
mkdir -p /var/www/deckstudio
chown openclaw:openclaw /var/www/deckstudio
chmod 755 /var/www/deckstudio

echo "==> Creating /opt/deckstudio data dirs..."
mkdir -p /opt/deckstudio/data/sessions
mkdir -p /opt/deckstudio/data/exports
mkdir -p /opt/deckstudio/backend
chown -R openclaw:openclaw /opt/deckstudio
chmod -R 755 /opt/deckstudio

echo "==> Installing nginx vhost (HTTP-only; certbot will add SSL)..."
cat > /etc/nginx/sites-available/deckstudio << 'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name deckstudio.karlekar.cloud;

    root /var/www/deckstudio;
    index index.html;

    location /api/ {
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_connect_timeout  30s;
        proxy_send_timeout    300s;
        proxy_read_timeout    300s;
        client_max_body_size 11M;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|woff2?|ttf|eot|svg|png|ico|webp)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location = /index.html {
        add_header Cache-Control "no-store, no-cache, must-revalidate";
        expires -1;
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/javascript;
    gzip_min_length 1024;
}
NGINX

ln -sf /etc/nginx/sites-available/deckstudio /etc/nginx/sites-enabled/deckstudio
/usr/sbin/nginx -t && systemctl reload nginx
echo "    nginx vhost installed and active."

echo "==> Installing systemd service..."
cat > /etc/systemd/system/deckstudio.service << 'SYSTEMD'
[Unit]
Description=DeckStudio Backend (FastAPI/uvicorn)
After=network.target

[Service]
Type=simple
User=openclaw
Group=openclaw
WorkingDirectory=/opt/deckstudio/backend
EnvironmentFile=/opt/deckstudio/backend/.env
ExecStart=/opt/deckstudio/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001 --workers 1 --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=deckstudio

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable deckstudio
echo "    systemd service installed and enabled."

echo ""
echo "==> Root setup complete. Spark will handle the rest."
