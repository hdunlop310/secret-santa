.PHONY: dev up api web test test-backend test-frontend e2e jobs lint migrate

UV = uv --directory backend

up:
	docker compose up -d --wait

dev: up migrate
	$(MAKE) -j2 api web

api:
	$(UV) run uvicorn app.main:app --reload --port 8000

web:
	npm --prefix frontend run dev

migrate:
	$(UV) run alembic upgrade head

test: test-backend test-frontend

test-backend:
	$(UV) run pytest

test-frontend:
	npm --prefix frontend test

# Needs `make dev` running, with RATE_LIMIT_GROUP_CREATE and RATE_LIMIT_EMAIL_SEND raised in .env
e2e:
	npm --prefix frontend run e2e

# Reminders, wish-list-changed emails and deleting old groups (run on a schedule in production)
jobs:
	$(UV) run python -m app.jobs

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	npm --prefix frontend run lint
