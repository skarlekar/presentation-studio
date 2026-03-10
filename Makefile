# DeckStudio — Deployment Makefile
# Usage:
#   make setup        One-time server setup (run as root)
#   make deploy       Full deploy: backend + frontend
#   make backend      Deploy backend only (code + deps + restart)
#   make frontend     Build + deploy frontend only
#   make restart      Restart the backend service
#   make logs         Tail live service logs
#   make status       Show service status
#   make ssl          Obtain/renew SSL cert via certbot
#   make test         Run backend tests locally
#   make test-fe      Run frontend tests locally

# ── Config ───────────────────────────────────────────────────────────────────
DOMAIN       := deckstudio.karlekar.cloud
APP_DIR      := /opt/deckstudio
STATIC_DIR   := /var/www/deckstudio
APP_USER     := deckstudio
BACKEND_SRC  := $(CURDIR)/backend
FRONTEND_SRC := $(CURDIR)/frontend
VENV         := $(APP_DIR)/venv
SERVICE      := deckstudio
PYTHON       := $(VENV)/bin/python3
PIP          := $(VENV)/bin/pip

# Colours
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RESET  := \033[0m

.PHONY: setup deploy backend frontend restart logs status ssl test test-fe help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-14s$(RESET) %s\n", $$1, $$2}'

# ── One-time setup ───────────────────────────────────────────────────────────
setup: ## One-time server setup (run as root: sudo make setup)
	@echo "$(YELLOW)==> Running server setup...$(RESET)"
	bash deploy/setup.sh

# ── Full deploy ──────────────────────────────────────────────────────────────
deploy: backend frontend restart ## Full deploy: backend + frontend + restart
	@echo "$(GREEN)==> Deploy complete! https://$(DOMAIN)$(RESET)"

# ── Backend ──────────────────────────────────────────────────────────────────
backend: ## Deploy backend (sync code + install deps)
	@echo "$(YELLOW)==> Deploying backend...$(RESET)"
	rsync -av --delete \
		--exclude '__pycache__' \
		--exclude '*.pyc' \
		--exclude '.pytest_cache' \
		--exclude 'coverage_html' \
		--exclude 'tests/' \
		--exclude '.env' \
		$(BACKEND_SRC)/ $(APP_DIR)/backend/
	@echo "$(YELLOW)==> Installing Python dependencies...$(RESET)"
	sudo -u $(APP_USER) $(PIP) install --quiet -r $(APP_DIR)/backend/requirements.txt
	@echo "$(GREEN)==> Backend deployed.$(RESET)"

# ── Frontend ─────────────────────────────────────────────────────────────────
frontend: ## Build React app and deploy to static dir
	@echo "$(YELLOW)==> Building frontend...$(RESET)"
	cd $(FRONTEND_SRC) && npm ci --silent && npm run build
	@echo "$(YELLOW)==> Deploying frontend to $(STATIC_DIR)...$(RESET)"
	rsync -av --delete $(FRONTEND_SRC)/dist/ $(STATIC_DIR)/
	chown -R www-data:www-data $(STATIC_DIR)
	@echo "$(GREEN)==> Frontend deployed.$(RESET)"

# ── Service management ───────────────────────────────────────────────────────
restart: ## Restart the deckstudio systemd service
	@echo "$(YELLOW)==> Restarting $(SERVICE)...$(RESET)"
	systemctl restart $(SERVICE)
	systemctl is-active --quiet $(SERVICE) && \
		echo "$(GREEN)==> Service is running.$(RESET)" || \
		(echo "ERROR: Service failed to start. Run 'make logs' to debug." && exit 1)

logs: ## Tail live service logs (Ctrl+C to exit)
	journalctl -u $(SERVICE) -f --no-pager

status: ## Show service status
	@systemctl status $(SERVICE) --no-pager || true
	@echo ""
	@echo "Backend health:"
	@curl -sf http://127.0.0.1:8001/api/health | python3 -m json.tool || echo "Backend not responding"

# ── SSL ──────────────────────────────────────────────────────────────────────
ssl: ## Obtain/renew SSL cert via certbot
	certbot --nginx -d $(DOMAIN) --non-interactive --agree-tos \
		--email admin@karlekar.cloud --redirect
	systemctl reload nginx
	@echo "$(GREEN)==> SSL cert installed and nginx reloaded.$(RESET)"

# ── Local development / testing ───────────────────────────────────────────────
test: ## Run backend tests locally
	cd backend && \
	PYTHONPATH=".:$(CURDIR)" \
	LLM_PROVIDER=openai \
	OPENAI_API_KEY=sk-test-dummy \
	DEEPAGENTS_CHECKPOINT_DB=./test.db \
	python3 -m pytest tests/ -v --tb=short

test-fe: ## Run frontend tests locally
	cd frontend && npm test -- --run
