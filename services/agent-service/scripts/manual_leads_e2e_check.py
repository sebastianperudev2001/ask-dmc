"""Manual E2E verification script for the BackOffice increment (Incremento 3) — drives
a real conversation against /ws/chat, sending enough user messages to push the lead
through the engagement floor (BR-17b: 5+ -> warm, 10+ -> hot), which should trigger
FR-6/FR-8 (live board broadcast) and FR-10 (auto-draft on hot) on a real running
agent-service. Meant to be watched from apps/backoffice in a browser at the same time."""
import asyncio
import json

import websockets

MESSAGES = [
    "Hola, quiero aprender data engineering en Azure.",
    "Tengo un presupuesto de 900 soles y quiero terminar en 10 semanas.",
    "Vengo de un background de analista de datos.",
    "Me interesa Azure Data Factory y Databricks.",
    "Cuanto dura el programa exactamente?",
    "Tienen certificacion al final?",
    "Puedo pagar en cuotas?",
    "Los profesores son de la industria?",
    "Hay clases en vivo o son grabadas?",
    "Perfecto, quiero inscribirme pronto.",
]


async def main():
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        for i, text in enumerate(MESSAGES, start=1):
            await ws.send(json.dumps({"type": "user_message", "text": text}))
            print(f"--- mensaje {i}/{len(MESSAGES)}: {text!r} ---")
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg["type"] == "turn_done":
                    print("  turn_done")
                    break
                if msg["type"] == "session_created":
                    print("  session_created:", msg["service_session_id"][:20], "conv:", msg["conversation_id"])


asyncio.run(main())
