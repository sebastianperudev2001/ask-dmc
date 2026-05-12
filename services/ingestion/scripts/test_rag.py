import json
import logging
import os
import sys

import psycopg2
import requests
from pgvector.psycopg2 import register_vector

from src.config import load_config
from src.infrastructure.embeddings.ollama_embeddings import OllamaEmbeddingsProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Fallback specifically for this test script based on user preference
os.environ.setdefault(
    "VECTOR_DB_URL", "postgresql://ask_dmc:ask_dmc@localhost:5433/ask_dmc"
)


def main():
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    logger.info(f"Connecting to vector DB at {config.vector_db_url}")
    try:
        conn = psycopg2.connect(config.vector_db_url)
        register_vector(conn)
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    embeddings_provider = OllamaEmbeddingsProvider(
        base_url=config.ollama_base_url,
        model=config.ollama_model,
    )

    llm_model = "gemma4"  # gemma3:4b by default or what's in config
    logger.info(f"Using embeddings model: {config.ollama_model}")
    logger.info(f"Using LLM model for generation: {llm_model}")
    print("\n" + "=" * 50)
    print("Welcome to the DMC Knowledge Base RAG Tester")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 50 + "\n")

    while True:
        try:
            question = input("\nQ: ")
        except (KeyboardInterrupt, EOFError):
            break

        if question.lower().strip() in ("exit", "quit"):
            break

        if not question.strip():
            continue

        try:
            # 1. Get embedding for the question
            question_embedding = embeddings_provider.embed(question)

            # 2. Query the vector database for closest chunks
            with conn.cursor() as cur:
                # Probe all IVFFlat lists — dataset is small so exhaustive scan is cheap
                cur.execute("SET ivfflat.probes = 10;")
                cur.execute(
                    """
                    SELECT
                        id,
                        course_name,
                        content,
                        embedding <=> %s::vector AS distance
                    FROM brochure_chunks
                    ORDER BY distance ASC
                    LIMIT 5;
                """,
                    (question_embedding,),
                )

                results = cur.fetchall()

            if not results:
                print("\nNo relevant information found in the database.")
                continue

            # 3. Construct context from results
            context_parts = []
            print("\n--- Retrieved Sources ---")
            for idx, (chunk_id, course_name, content, distance) in enumerate(results, 1):
                # Extract section type from chunk ID: "{course_name}__{section_type}[__{i}]"
                section_type = chunk_id.split("__")[1] if "__" in chunk_id else "unknown"
                print(f"{idx}. {course_name} / {section_type} (Distance: {distance:.4f})")
                context_parts.append(
                    f"Curso: {course_name}\nSección: {section_type}\nContenido:\n{content}"
                )

            context = "\n\n".join(context_parts)

            prompt = f"""Eres un asesor educativo experto de DMC Institute.
Tu objetivo es responder de manera clara y persuasiva a las dudas de los interesados sobre nuestros programas y cursos.
Utiliza ÚNICAMENTE la información proporcionada en el siguiente contexto extraído de nuestros brochures.
Si la información solicitada no se encuentra en el contexto, indica amablemente que no tienes ese dato exacto y sugiere contactar al equipo comercial al +51 912 322 976.
No inventes precios, fechas ni temarios que no estén en el contexto.

Contexto de los brochures:
{context}

Pregunta del usuario: {question}

Respuesta:"""

            # 5. Stream the response from Ollama
            print("\nA: ", end="", flush=True)

            url = f"{config.ollama_base_url.rstrip('/')}/api/generate"
            payload = {
                "model": llm_model,
                "prompt": prompt,
                "stream": True,
                "keep_alive": "5m",
            }

            response = requests.post(url, json=payload, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    chunk = data.get("response", "")
                    print(chunk, end="", flush=True)
                    if data.get("done"):
                        break

            print("\n" + "-" * 50)

        except Exception as e:
            logger.error(f"Error processing question: {e}")

    logger.info("Closing connection.")
    conn.close()


if __name__ == "__main__":
    main()
