SHELL := /bin/zsh

PNPM ?= pnpm
UV ?= uv
COMPOSE_FILE ?= infra/compose/docker-compose.dev.yml
PROD_COMPOSE_FILE ?= infra/compose/docker-compose.prod.yml
PROD_ENV_FILE ?= infra/compose/.env.prod

.PHONY: infra-up infra-down infra-logs frontend-dev backend-sync backend-migrate backend-dev api-dev worker-dev format prod-config prod-build prod-up prod-down prod-logs prod-migrate prod-release prod-release-with-migrate

infra-up:
	docker compose --env-file infra/compose/.env.example -f $(COMPOSE_FILE) up -d
	./scripts/verify-dev-infra.sh

infra-down:
	docker compose --env-file infra/compose/.env.example -f $(COMPOSE_FILE) down -v

infra-logs:
	docker compose --env-file infra/compose/.env.example -f $(COMPOSE_FILE) logs -f

frontend-dev:
	cd frontend && $(PNPM) install && $(PNPM) dev

backend-sync:
	cd backend && $(UV) sync

backend-migrate:
	cd backend && $(UV) run alembic upgrade head

backend-dev:
	./scripts/dev-backend.sh

api-dev:
	cd backend && $(UV) run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

worker-dev:
	cd backend && $(UV) run python -m apps.worker.dev

format:
	cd backend && $(UV) run ruff format .

prod-config:
	docker compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) config

prod-build:
	docker compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) build frontend api worker

prod-up:
	docker compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) up -d --remove-orphans

prod-down:
	docker compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) down

prod-logs:
	docker compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) logs -f

prod-migrate:
	docker compose --env-file $(PROD_ENV_FILE) -f $(PROD_COMPOSE_FILE) run --rm api alembic upgrade head

prod-release:
	ENV_FILE=$(PROD_ENV_FILE) COMPOSE_FILE=$(PROD_COMPOSE_FILE) ./scripts/release.sh

prod-release-with-migrate:
	ENV_FILE=$(PROD_ENV_FILE) COMPOSE_FILE=$(PROD_COMPOSE_FILE) ./scripts/release.sh --migrate
