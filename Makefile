.PHONY: api web sync up down logs build ps restart dev

# Production: see deploy/README.md (GHCR + free-tier EC2 + DuckDNS)

# --- Local hot-reload (edit code → see it immediately) ---
# UI:  http://localhost:3000
# API: http://localhost:8001
# Tip: stop Docker UI/API first so you don't edit against a stale image:
#   docker compose stop api

dev:
	@echo "Starting hot-reload stack…"
	@echo "  UI  → http://localhost:3000  (Vite HMR)"
	@echo "  API → http://localhost:8001  (uvicorn --reload)"
	@echo "Stop Docker api if needed: docker compose stop api"
	@lsof -tiTCP:8001 -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null || true
	@lsof -tiTCP:3000 -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null || true
	@cd apps/api && API_CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000' \
		.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8001 &
	@cd apps/web && npm run dev -- --host 127.0.0.1 --port 3000

api:
	cd apps/api && API_CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000' \
		.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

web:
	cd apps/web && npm run dev -- --host 127.0.0.1 --port 3000

sync:
	curl -s -X POST 'http://127.0.0.1:8001/api/jobs/sync?query=software%20engineer'

# --- Docker (built image — rebuild to pick up code changes) ---
# App: http://localhost:8000  ·  Learning list: http://localhost:8000/learning-list

up: build
	docker compose up -d
	@echo ""
	@echo "Lernyra is starting → http://localhost:8000"
	@echo "Learning list     → http://localhost:8000/learning-list"
	@echo "API health        → http://localhost:8000/api/health"
	@echo "For instant local edits use: make api & make web → http://localhost:3000"
	@echo "Logs: make logs"

build:
	docker compose build

down:
	docker compose down

restart:
	docker compose restart api

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps
