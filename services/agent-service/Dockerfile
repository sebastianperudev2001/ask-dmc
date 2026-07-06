# Pinned base image tag — SECURITY-10: never `latest` in production images.
FROM python:3.11.10-slim-bookworm

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY main.py ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
