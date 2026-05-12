from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator
from contextlib import asynccontextmanager

import psycopg2
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pgvector.psycopg2 import register_vector
from pydantic import BaseModel

from src.config import ApiConfig, load_config

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_config: ApiConfig | None = None
_conn: psycopg2.extensions.connection | None = None

SYSTEM_PROMPT = """Eres un asesor educativo experto de DMC Institute.
Tu objetivo es responder de manera clara y persuasiva a las dudas de los interesados sobre nuestros programas y cursos.
Utiliza ÚNICAMENTE la información proporcionada en el siguiente contexto extraído de nuestros brochures.
Si la información solicitada no se encuentra en el contexto, indica amablemente que no tienes ese dato exacto y sugiere contactar al equipo comercial al +51 912 322 976.
No inventes precios, fechas ni temarios que no estén en el contexto."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config, _conn
    _config = load_config()
    _conn = psycopg2.connect(_config.vector_db_url)
    register_vector(_conn)
    logger.info("Connected to vector DB")
    yield
    if _conn:
        _conn.close()
        logger.info("DB connection closed")


app = FastAPI(title="DMC RAG API", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str


def _embed(question: str) -> list[float]:
    url = f"{_config.ollama_base_url.rstrip('/')}/api/embeddings"
    payload = {
        "model": _config.ollama_embeddings_model,
        "prompt": f"search_query: {question}",
        "keep_alive": "10m",
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    if "embedding" not in body:
        raise RuntimeError(f"Ollama embeddings error: {body}")
    return body["embedding"]


def _retrieve(embedding: list[float]) -> list[tuple]:
    with _conn.cursor() as cur:
        cur.execute("SET ivfflat.probes = 10;")
        cur.execute(
            """
            SELECT id, course_name, content, embedding <=> %s::vector AS distance
            FROM brochure_chunks
            ORDER BY distance ASC
            LIMIT %s;
            """,
            (embedding, _config.rag_top_k),
        )
        return cur.fetchall()


def _build_prompt(question: str, chunks: list[tuple]) -> str:
    context_parts = []
    for chunk_id, course_name, content, _ in chunks:
        section_type = chunk_id.split("__")[1] if "__" in chunk_id else "general"
        context_parts.append(f"Curso: {course_name}\nSección: {section_type}\nContenido:\n{content}")

    context = "\n\n".join(context_parts)
    return f"{SYSTEM_PROMPT}\n\nContexto de los brochures:\n{context}\n\nPregunta del usuario: {question}\n\nRespuesta:"


def _stream_ollama(prompt: str) -> Generator[str, None, None]:
    url = f"{_config.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": _config.ollama_llm_model,
        "prompt": prompt,
        "stream": True,
        "keep_alive": "5m",
    }
    with requests.post(url, json=payload, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                chunk = data.get("response", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    try:
        embedding = _embed(req.question)
        chunks = _retrieve(embedding)
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Retrieval failed")

    if not chunks:
        raise HTTPException(status_code=404, detail="No relevant information found")

    prompt = _build_prompt(req.question, chunks)

    return StreamingResponse(
        _stream_ollama(prompt),
        media_type="text/plain",
        headers={"X-Sources": json.dumps([
            {"course": c[1], "section": c[0].split("__")[1] if "__" in c[0] else "general", "distance": round(c[3], 4)}
            for c in chunks
        ])},
    )
