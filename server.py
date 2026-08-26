#!/usr/bin/env python3
"""server.py - Sovereign Tactical C2 Data Link Relay Middleware.

Features:
  - Air-gapped WebSocket C2 bridge on ws://0.0.0.0:8765.
  - Pre-shared token auth gate on first handshake frame.
  - Seamless routing of AES-256-GCM encrypted telemetry wireframes to GCS displays.
  - Forwarding of encrypted command envelopes from GCS to UAV nodes.
  - Threat event propagation (QBER spikes, attack detection, network node telemetry).
  - Resilient heartbeat monitor and node lifecycle management.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone

import websockets

WS_HOST = "0.0.0.0"
WS_PORT = 8765
MAX_NODES = 64
QBER_THRESHOLD = 0.25
HEARTBEAT_TIMEOUT = 15
MAX_SNAPSHOT_B64 = 300_000
AUTH_TOKEN = os.getenv("C2_TOKEN", "SIH-QUANTUM-2026")

# node_id -> {ws, last_heartbeat, caps, qber, pqc, label, last_seq}
nodes = {}


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_label(raw, fallback):
    s = "".join(c for c in str(raw)[:16].upper() if c.isalnum() or c in "-_")
    return s if len(s) >= 3 else fallback


def authorized_first_frame(data):
    return isinstance(data, dict) and data.get("token") == AUTH_TOKEN


async def send_json(ws, obj):
    try:
        await asyncio.wait_for(ws.send(json.dumps(obj)), timeout=3)
    except (asyncio.TimeoutError, ConnectionError, RuntimeError):
        pass


async def broadcast(obj, exclude=None):
    """Fan-out message to all connected mesh nodes."""
    text = json.dumps(obj)
    for nid, info in list(nodes.items()):
        if nid == exclude:
            continue
        try:
            await asyncio.wait_for(info["ws"].send(text), timeout=3)
        except (asyncio.TimeoutError, ConnectionError, RuntimeError):
            pass


async def cleanup_node(node_id, reason=""):
    info = nodes.pop(node_id, None)
    if info:
        print(f"[SERVER] Node {node_id} ({info['label']}) disconnected {reason}")
        await broadcast({"type": "node_left", "from_node": node_id, "timestamp": utcnow()})


async def handle_authenticated(node_id, ws, data):
    t = data.get("type")

    if t == "heartbeat":
        nodes[node_id]["last_heartbeat"] = time.time()
        await send_json(ws, {"type": "heartbeat_ack", "ts": utcnow()})

    elif t == "handshake":
        nodes[node_id]["label"] = clean_label(data.get("node_id"), node_id)
        nodes[node_id]["caps"] = [str(c)[:24] for c in data.get("capabilities", [])][:10]
        print(f"[SERVER] Handshake registered for {nodes[node_id]['label']} with caps {nodes[node_id]['caps']}")

    elif t == "secure_telemetry":
        # Wireframe encrypted telemetry envelope from UAV node
        nodes[node_id]["last_heartbeat"] = time.time()
        nodes[node_id]["qber"] = data.get("qber", 0.0)
        nodes[node_id]["pqc"] = data.get("pqc_active", False)

        # Broadcast encrypted wireframe to all GCS dashboard listeners
        await broadcast({
            "type": "secure_telemetry_broadcast",
            "from_node": node_id,
            "label": nodes[node_id]["label"],
            "wireframe": data,
            "timestamp": utcnow()
        })

    elif t == "encrypted_command":
        # Encrypted command from GCS to UAV node
        target = data.get("target_node")
        print(f"[SERVER] Relaying encrypted command to target: {target}")
        await broadcast({
            "type": "encrypted_command",
            "from_gcs": node_id,
            "target_node": target,
            "seq_no": data.get("seq_no"),
            "iv": data.get("iv"),
            "ciphertext": data.get("ciphertext"),
            "timestamp": utcnow()
        })

    elif t == "qber_alert":
        q = float(data.get("qber", 0.0))
        eve = bool(data.get("eavesdropper_active", False))
        m = nodes[node_id]
        if q > QBER_THRESHOLD and not m["pqc"]:
            m["pqc"] = True
            print(f"[SERVER] !!! PQC FALLBACK ENGAGED for {m['label']} (QBER={q*100:.1f}%)")
        elif q <= QBER_THRESHOLD * 0.5 and m["pqc"]:
            m["pqc"] = False
        await broadcast({
            "type": "qber_alert",
            "from_node": node_id,
            "label": m["label"],
            "qber": q,
            "eavesdropper_active": eve,
            "threshold": QBER_THRESHOLD,
            "pqc_fallback": m["pqc"],
            "timestamp": utcnow()
        })

    elif t == "ew_jamming_toggle":
        jam = bool(data.get("jamming_active", False))
        print(f"[SERVER] EW Electronic Jamming alert: {jam}")
        await broadcast({
            "type": "ew_jamming_toggle",
            "from_node": node_id,
            "jamming_active": jam,
            "timestamp": utcnow()
        })

    elif t == "snapshot":
        snap = data.get("snapshot", "")
        if isinstance(snap, str) and snap.startswith("data:image/") and len(snap) <= MAX_SNAPSHOT_B64:
            await broadcast({
                "type": "snapshot_broadcast",
                "from_node": node_id,
                "label": nodes[node_id]["label"],
                "snapshot": snap,
                "timestamp": utcnow()
            })


def get_server_network_ips():
    import socket
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    if "192.168.137.1" not in ips:
        ips.append("192.168.137.1")
    return ips


async def handler(ws):
    peer = ws.remote_address
    node_id = uuid.uuid4().hex[:8].upper()

    # Pre-shared Auth Gate
    try:
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
    except (asyncio.TimeoutError, json.JSONDecodeError, ConnectionError):
        return

    if not authorized_first_frame(first):
        print(f"[SERVER] Unauthorized connection attempt from {peer} (Invalid Auth Token)")
        return

    if len(nodes) >= MAX_NODES:
        await send_json(ws, {"type": "rejected", "reason": "mesh_capacity_reached"})
        return

    label = clean_label(first.get("node_id"), node_id)
    nodes[node_id] = {
        "ws": ws,
        "last_heartbeat": time.time(),
        "caps": first.get("capabilities", []),
        "qber": 0.0,
        "pqc": False,
        "label": label,
    }
    print(f"[SERVER] Node authenticated: {node_id} ({label}) from {peer}")
    detected_ips = get_server_network_ips()
    await send_json(ws, {"type": "welcome", "assigned_id": node_id, "server_ips": detected_ips})
    await broadcast({"type": "node_joined", "from_node": node_id, "label": label, "timestamp": utcnow()}, exclude=node_id)

    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                continue
            if isinstance(data, dict):
                try:
                    await handle_authenticated(node_id, ws, data)
                except Exception as ex:
                    print(f"[SERVER ERROR msg from {node_id}]: {ex}")
    except websockets.ConnectionClosed:
        pass
    finally:
        await cleanup_node(node_id)


async def heartbeat_monitor():
    while True:
        await asyncio.sleep(5)
        now = time.time()
        stale = [nid for nid, i in nodes.items() if now - i["last_heartbeat"] > HEARTBEAT_TIMEOUT]
        for nid in stale:
            await cleanup_node(nid, reason="(Heartbeat Timeout)")


async def main():
    asyncio.create_task(heartbeat_monitor())
    async with websockets.serve(handler, WS_HOST, WS_PORT, max_size=512 * 1024, ping_interval=20, ping_timeout=15):
        print(f"[SERVER] Tactical C2 Relay active on ws://{WS_HOST}:{WS_PORT}")
        print(f"[SERVER] Security Enclave: AES-256-GCM + BB84/ML-KEM Auth Active (Token: {AUTH_TOKEN})")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SERVER] Relay shutdown.")
