SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PNPM ?= pnpm
UV ?= uv
DOCKER ?= docker
COMPOSE_FILE ?= infra/compose/docker-compose.dev.yml
PROD_COMPOSE_FILE ?= infra/compose/docker-compose.prod.yml
PROD_ENV_FILE ?= infra/compose/.env.prod
DEV_ENV_FILE ?= infra/compose/.env.example

.PHONY: \
	help \
	dev \
	infra.up infra.down infra.logs \
	backend.migrate backend.dev backend.api backend.worker backend.test \
	frontend.dev \
	format \
	prod.config prod.build prod.up prod.down prod.logs prod.migrate prod.release prod.release-with-migrate \
	infra-up infra-down infra-logs backend-migrate backend-dev api-dev worker-dev frontend-dev \
	prod-config prod-build prod-up prod-down prod-logs prod-migrate prod-release prod-release-with-migrate

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ { printf "  %-28s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

dev: ## Start backend API/worker and frontend dev server (infra must already be running)
	./scripts/dev-stack.sh

# ----- Infrastructure -------------------------------------------------------

infra.up: ## Start local infrastructure (Docker Compose)
	@command -v $(DOCKER) >/dev/null || { echo "Error: '$(DOCKER)' is not installed or not in PATH."; exit 127; }
	$(DOCKER) compose --env-file $(DEV_ENV_FILE) -f $(COMPOSE_FILE) up -d
	./scripts/verify-dev-infra.sh

infra.down: ## Stop and remove local infrastructure volumes
	@command -v $(DOCKER) >/dev/null || { echo "Error: '$(DOCKER)' is not installed or not in PATH."; exit 127; }
	$(DOCKER) compose --env-file $(DEV_ENV_FILE) -f $(COMPOSE_FILE) down -v

infra.logs: ## Tail local infrastructure logs
	@command -v $(DOCKER) >/dev/null || { echo "Error: '$(DOCKER)' is not installed or not in PATH."; exit 127; }
	$(DOCKER) compose --env-file $(DEV_ENV_FILE) -f $(COMPOSE_FILE) logs -f

# ----- Backend --------------------------------------------------------------

backend.migrate: ## Run backend DB migrations
	cd backend && $(UV) sync
	cd backend && PYTHONPATH=src $(UV) run python -m alembic upgrade head

backend.dev: ## Start backend API + worker dev processes
	./scripts/dev-backend.sh

backend.api: ## Start backend API only
	cd backend && $(UV) sync
	cd backend && PYTHONPATH=src $(UV) run python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

backend.worker: ## Start backend worker only
	cd backend && $(UV) sync
	cd backend && $(UV) run python -m apps.worker.dev

backend.test: ## Run backend tests
	cd backend && $(UV) run pytest -q

# ----- Frontend -------------------------------------------------------------

frontend.dev: ## Install frontend deps and run Next.js dev server
	cd frontend && $(PNPM) install && $(PNPM) dev

format: ## Format backend code with Ruff
	cd backend && $(UV) run ruff format .

# ----- Production -----------------------------------------------------------

prod.config: ## Render production compose config
	$(DOCKER) compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) config

prod.build: ## Build production images
	$(DOCKER) compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) build frontend api worker

prod.up: ## Start production stack
	$(DOCKER) compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) up -d --remove-orphans

prod.down: ## Stop production stack
	$(DOCKER) compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) down

prod.logs: ## Tail production logs
	$(DOCKER) compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) logs -f

prod.migrate: ## Run production migrations
	$(DOCKER) compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) run --rm api alembic upgrade head

prod.release: ## Release production without migration
	ENV_FILE=$(PROD_ENV_FILE) COMPOSE_FILE=$(PROD_COMPOSE_FILE) ./scripts/release.sh

prod.release-with-migrate: ## Release production and run migration
	ENV_FILE=$(PROD_ENV_FILE) COMPOSE_FILE=$(PROD_COMPOSE_FILE) ./scripts/release.sh --migrate

# ----- Backward compatible aliases -----------------------------------------

infra-up: infra.up ## Alias: infra.up
infra-down: infra.down ## Alias: infra.down
infra-logs: infra.logs ## Alias: infra.logs
backend-migrate: backend.migrate ## Alias: backend.migrate
backend-dev: backend.dev ## Alias: backend.dev
api-dev: backend.api ## Alias: backend.api
worker-dev: backend.worker ## Alias: backend.worker
frontend-dev: frontend.dev ## Alias: frontend.dev
prod-config: prod.config ## Alias: prod.config
prod-build: prod.build ## Alias: prod.build
prod-up: prod.up ## Alias: prod.up
prod-down: prod.down ## Alias: prod.down
prod-logs: prod.logs ## Alias: prod.logs
prod-migrate: prod.migrate ## Alias: prod.migrate
prod-release: prod.release ## Alias: prod.release
prod-release-with-migrate: prod.release-with-migrate ## Alias: prod.release-with-migrate
