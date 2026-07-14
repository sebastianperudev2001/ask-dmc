"""Debug script: simulates user filling the form with a human delay (3 seconds)
before clicking Confirmar. Tests whether the profile_data_submitted message is
correctly processed after a delay — which is different from the manual_chat_check.py
which submits immediately."""
import asyncio
import json
import time

import websockets


async def main():
    print("Connecting to ws://localhost:8000/ws/chat ...")
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        start = time.monotonic()

        # Send initial message
        await ws.send(json.dumps({
            "type": "user_message",
            "text": "quiero un curso de data engineering",
        }))
        print(f"[{time.monotonic()-start:.2f}s] Sent user_message")

        profile_requested_msg = None

        # Wait for profile_data_requested
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            msg = json.loads(raw)
            print(f"[{time.monotonic()-start:.2f}s] Received: type={msg['type']}", flush=True)

            if msg["type"] == "profile_data_requested":
                profile_requested_msg = msg
                print(f"  call_id={msg['call_id']}, prefill={msg['prefill']}")
                break
            elif msg["type"] == "recommendation_delta":
                print(f"  delta: {msg['delta'][:60]}...")

        if profile_requested_msg is None:
            print("ERROR: Never got profile_data_requested")
            return

        # Simulate human delay of 3 seconds (like filling the form)
        print(f"[{time.monotonic()-start:.2f}s] Simulating user filling form (3s delay)...")
        await asyncio.sleep(3)

        # Submit profile data
        payload = {
            "type": "profile_data_submitted",
            "call_id": profile_requested_msg["call_id"],
            "budget": 800.0,
            "max_duration_weeks": 10,
            "professional_background": "Analista de datos",
            "desired_stack": "Azure Data Engineering",
            "name": "Debug User",
            "email": "debug@example.com",
        }
        await ws.send(json.dumps(payload))
        print(f"[{time.monotonic()-start:.2f}s] Sent profile_data_submitted: {payload}")

        # Wait for continuation
        full_text = ""
        timeout_remaining = 30
        t_after_submit = time.monotonic()
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_remaining)
            except asyncio.TimeoutError:
                print(f"[{time.monotonic()-start:.2f}s] TIMEOUT waiting for response after submit!")
                break

            msg = json.loads(raw)
            print(f"[{time.monotonic()-start:.2f}s] Received: type={msg['type']}", flush=True)

            if msg["type"] == "recommendation_delta":
                full_text += msg["delta"]
                print(f"  delta: {msg['delta'][:80]}")
            elif msg["type"] == "turn_done":
                print(f"  TURN DONE after {time.monotonic()-t_after_submit:.2f}s")
            elif msg["type"] == "session_created":
                print(f"  SESSION: {msg['service_session_id']}")
                print(f"\n--- Full text ---\n{full_text}\n")
                break
            elif msg["type"] == "recommendation_done":
                print(f"  CANDIDATES: {msg['candidates']}")


asyncio.run(main())
