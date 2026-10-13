.PHONY: sync dev test smoke up down logs

sync:
	uv sync

dev:
	uv run uvicorn taas.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest

smoke:
	uv run python scripts/smoke.py

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f dashboard
