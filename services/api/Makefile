ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: install run

install:
	uv sync

run:
	PYTHONPATH=. uv run uvicorn main:app --reload --port 8000
