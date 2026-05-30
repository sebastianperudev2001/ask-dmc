from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel

from src.config import load_config
from src.domain.entities import ApiConfig, CourseMetadata
from src.tools import get_course_details, init_tools, list_courses

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un asesor educativo experto de DMC Institute.
Tu objetivo es orientar al visitante entre el catálogo de cursos, recomendar programas según su perfil y objetivos, y responder preguntas sobre contenido, duración y precios.
Usa las herramientas disponibles para consultar el catálogo antes de responder.
Si la información no está disponible en las herramientas, indica amablemente que no tienes ese dato y sugiere contactar al equipo comercial al +51 912 322 976.
No inventes precios, fechas ni temarios que no estén provistos por las herramientas.
Responde siempre en el mismo idioma en que el usuario te escribe."""

_config: ApiConfig | None = None


def _load_courses(metadata_path: str) -> list[CourseMetadata]:
    with open(metadata_path) as f:
        raw = json.load(f)
    return [
        CourseMetadata(
            id=doc["id"],
            title=doc["title"],
            program_type=doc["program_type"],
            aliases=doc.get("aliases", []),
            keywords=doc.get("keywords", []),
            topics=doc.get("topics", []),
        )
        for doc in raw["documents"]
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config
    _config = load_config()
    courses = _load_courses(_config.metadata_path)
    init_tools(courses)
    logger.info(f"Agent initialized — {len(courses)} courses loaded")
    yield


app = FastAPI(title="DMC Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


def _make_agent() -> Agent:
    model = BedrockModel(
        model_id=_config.bedrock_model_id,
        region_name=_config.aws_region,
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[list_courses, get_course_details],
        callback_handler=None,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
async def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    agent = _make_agent()

    async def generate():
        try:
            async for event in agent.stream_async(req.question):
                if "data" in event:
                    yield event["data"]
        except Exception as e:
            logger.error(f"Agent error: {e}")
            yield "\n[Error al generar la respuesta. Por favor intenta de nuevo.]"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
