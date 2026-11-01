.PHONY: dev up api web test test-backend test-frontend lint migrate

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

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	npm --prefix frontend run lint
