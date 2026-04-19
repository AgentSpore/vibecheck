.PHONY: install dev run smoke test docker

install:
	uv sync --extra dev

test:
	uv run --extra dev pytest -q

dev:
	uv run uvicorn vibecheck.main:app --host 0.0.0.0 --port 8895 --reload

run:
	uv run uvicorn vibecheck.main:app --host 0.0.0.0 --port 8895

smoke:
	uv run python smoke_test.py

docker:
	docker build -t vibecheck:local .
	docker run --rm -p 8895:8895 --env-file .env vibecheck:local
