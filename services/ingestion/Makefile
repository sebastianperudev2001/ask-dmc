.PHONY: install test test-unit test-pbt run db-up db-down lint

install:
	pip install -r requirements-dev.txt

test:
	PYTHONPATH=. pytest tests/ -v --tb=short

test-unit:
	PYTHONPATH=. pytest tests/unit/ -v --tb=short

test-pbt:
	PYTHONPATH=. pytest tests/pbt/ -v --tb=short

run:
	PYTHONPATH=. python cli.py

db-up:
	docker compose up -d

db-down:
	docker compose down

lint:
	python -m py_compile src/**/*.py cli.py lambda_handler.py
