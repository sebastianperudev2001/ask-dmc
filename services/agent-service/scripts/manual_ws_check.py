import asyncio
import json
import time

import websockets


async def main():
    async with websockets.connect("ws://localhost:8123/ws/recommendation") as ws:
        start = time.monotonic()
        await ws.send(json.dumps({
            "type": "recommendation_request",
            "budget": "3000.00",
            "max_duration_weeks": 10,
            "professional_background": "Data Engineer en Yape, proyecto de recomendación de productos",
            "desired_stack": "Data Science",
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
            elif msg["type"] == "relax_filters_offer":
                print("OFFER:", msg["message"])
            elif msg["type"] in ("recommendation_done", "no_recommendation", "no_exact_match_showing_all"):
                print("EVENT:", msg["type"], msg)
                if msg["type"] == "recommendation_done":
                    print("\n--- texto completo ---")
                    print(full_text)
                    break
                if msg["type"] == "no_recommendation":
                    break

asyncio.run(main())
