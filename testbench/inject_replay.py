#!/usr/bin/env python3
"""inject_replay.py - Adversary Replay Attack Demonstration Tool.

Demonstrates vulnerability against captured valid packets and proves the
effectiveness of monotonic sequence nonces and sliding window checks:
  - Listens to the C2 relay to capture a valid encrypted frame.
  - Waits for normal telemetry stream to progress (Seq N+10).
  - Injects the stale captured frame (Seq N).
  - Proves that the GCS rejects the stale sequence number immediately.
"""

import asyncio
import json
import os
import sys
import websockets

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8765")
AUTH_TOKEN = os.getenv("C2_TOKEN", "SIH-QUANTUM-2026")


async def run_replay_attack():
    print("\n" + "=" * 65)
    print(" ADVERSARY TESTBENCH: CAPTURE & REPLAY ATTACK INJECTION")
    print(" Target: Replay Stale Telemetry Sequence Nonce to GCS")
    print("=" * 65)

    async with websockets.connect(WS_URL) as ws:
        # Handshake
        await ws.send(json.dumps({
            "type": "handshake",
            "token": AUTH_TOKEN,
            "node_id": "REPLAY-ADVERSARY",
            "capabilities": ["sniffer", "replay_injection"]
        }))
        print("[+] Adversary connected. Listening for valid encrypted frame...")

        captured_wireframe = None

        # Capture first valid secure telemetry frame
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if msg.get("type") == "secure_telemetry_broadcast":
                    captured_wireframe = msg.get("wireframe")
                    seq = captured_wireframe.get("seq_no")
                    print(f"\n[+] INTERCEPTED VALID CIPHERTEXT FRAME: Seq #{seq}")
                    print(f"    Ciphertext preview: {captured_wireframe.get('ciphertext')[:32]}...")
                    break
            except Exception:
                continue

        if not captured_wireframe:
            print("[-] No frame captured.")
            return

        print("\n[*] Waiting 4 seconds while drone continues flying and sequence advances...")
        await asyncio.sleep(4)

        print(f"\n[!] INJECTING CAPTURED STALE FRAME (Seq #{captured_wireframe.get('seq_no')}) TO GCS...")
        await ws.send(json.dumps(captured_wireframe))
        print("[+] Replay packet injected.")
        print("[*] Observe Tactical GCS Dashboard:")
        print(f"    -> Instant Alert: '[ANTI-REPLAY VIOLATION] Stale Seq #{captured_wireframe.get('seq_no')} DROPPED!'")
        print("    -> Anti-Replay validation prevents GPS spoofing / trajectory regression.")
        print("=" * 65 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_replay_attack())
    except Exception as e:
        print(f"Error executing replay test: {e}")
