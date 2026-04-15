.PHONY: install dev run smoke docker

install:
	uv sync

dev:
	uv run uvicorn vibecheck.main:app --host 0.0.0.0 --port 8895 --reload

run:
	uv run uvicorn vibecheck.main:app --host 0.0.0.0 --port 8895

smoke:
	uv run python smoke_test.py

docker:
	docker build -t vibecheck:local .
	docker run --rm -p 8895:8895 --env-file .env vibecheck:local
