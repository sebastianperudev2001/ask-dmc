"""Manual verification script for /ws/chat (Incremento 2) — real WS client against a
locally running `uvicorn main:app`, exercising free chat + tool-calling end-to-end
against the real Foundry agent and Mercado Pago sandbox. Auto-confirms the
profile_data_requested widget with the agent's own prefill (no human in the loop for
this scripted run) so the whole flow can be driven unattended, same spirit as
manual_ws_check.py from incremento 1."""
import asyncio
import json
import time

import websockets


async def main():
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        start = time.monotonic()
        await ws.send(json.dumps({
            "type": "user_message",
            "text": (
                "Hola, quiero aprender data engineering, tengo un presupuesto de 800 soles "
                "y quiero terminar en 10 semanas, vengo de un background de analista de "
                "datos y quiero aprender Azure."
            ),
        }))

        first = True
        full_text = ""
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if first:
                print(f"[primer mensaje en {time.monotonic()-start:.2f}s] type={msg['type']}")
                first = False

            if msg["type"] == "recommendation_delta":
                full_text += msg["delta"]
            elif msg["type"] == "profile_data_requested":
                print("TOOL-CALL profile_data_requested:", msg["prefill"])
                await ws.send(json.dumps({
                    "type": "profile_data_submitted",
                    "call_id": msg["call_id"],
                    **msg["prefill"],
                }))
            elif msg["type"] == "recommendation_done":
                print("\n--- texto hasta ahora ---")
                print(full_text)
                full_text = ""
                print("CANDIDATES:", msg["candidates"])
            elif msg["type"] == "payment_link_created":
                print("PAYMENT LINK:", msg["checkout_url"])
            elif msg["type"] == "session_created":
                print("SESSION:", msg["service_session_id"])
                print("\n--- texto final ---")
                print(full_text)
                break


asyncio.run(main())