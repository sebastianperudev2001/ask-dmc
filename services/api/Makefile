ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: install run

install:
	pip install -r requirements.txt

run:
	PYTHONPATH=. uvicorn main:app --reload --port 8000
