#!/usr/bin/env python3
"""unified_runner.py - Sovereign Master Enclave Process Runner.

Coordinates all 3 core enclave services in ONE process:
  1. Sovereign WebSocket C2 Relay (ws://0.0.0.0:8765)
  2. Air-Gapped HTTP Static File Server (http://0.0.0.0:8000)
  3. Edge UAV Flight Dynamics & Cryptographic SITL Engine

Binds to 0.0.0.0 so physical smartphones on Wi-Fi or Hotspot can connect.
"""

import asyncio
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import time
from datetime import datetime, timezone

import websockets

from drone_simulator import (
    AUTH_TOKEN,
    NODE_ID,
    SWARM_FLEET,
    TICK_INTERVAL,
    crypto_engine,
    drone_flight,
    telemetry_sender_loop,
    command_receiver_loop,
)
from server import (
    WS_HOST,
    WS_PORT,
    handler as server_handler,
    heartbeat_monitor,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

HTTP_PORT = 8000


def get_local_ip_addresses():
    """Detect real physical network IP addresses for phone hotspot/Wi-Fi."""
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


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Quiet HTTP request handler with CORS headers enabled for mobile PWAs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        if self.path in ("", "/"):
            self.path = "/index.html"
        super().do_GET()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # Keep console output clean


def start_http_server():
    """Run HTTP static server in a dedicated daemon thread."""
    try:
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("0.0.0.0", HTTP_PORT), QuietHTTPHandler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        print(f"[HTTP SERVER ERROR] {e}")


def print_banner(local_ips):
    print("\n" + "=" * 78)
    print("  SOVEREIGN AIR-GAPPED QUANTUM-RESILIENT DRONE TELEMETRY & C2 ENCLAVE")
    print("  Smart India Hackathon (SIH) | MoD / DRDO / DGCA Aerospace Architecture")
    print("=" * 78)
    print(f"  [✓] C2 Relay Server        : ws://0.0.0.0:{WS_PORT}")
    print(f"  [✓] Tactical HTTP Server   : http://localhost:{HTTP_PORT}/index.html")
    print(f"  [✓] Multi-UAV Swarm Fleet  : {len(SWARM_FLEET)} Drones Online (AES-256-GCM + BB84/ML-KEM + FHSS)")
    for d in SWARM_FLEET:
        print(f"       • {d.node_id:<15} [{d.callsign}]")
    print("-" * 78)
    print("  📱 SMARTPHONE HOTSPOT / WI-FI DIRECT LINKS:")
    for ip in local_ips:
        print(f"     -> http://{ip}:{HTTP_PORT}/phone_client.html")
    print("=" * 78)
    print("  LIVE KEYBOARD CONTROLS (Type key + Enter):")
    print("    [E] Toggle Eve Eavesdropper (25% QBER -> ML-KEM PQC Key Rotation)")
    print("    [T] Inject Tampered Bit (Auth Tag Mismatch Test)")
    print("    [R] Inject Replay Packet (Stale Nonce Test)")
    print("    [J] Toggle EW RF Jamming (Activates FHSS Anti-Jamming Channel Hopping)")
    print("    [S] Toggle Swarm Patrol Formation")
    print("    [G] Simulate Geofence Breach (Forces Auto-RTL)")
    print("    [Q] Shutdown All Enclave Services")
    print("=" * 78 + "\n")


def stdin_listener(loop):
    while True:
        try:
            line = input().strip().lower()
            if not line:
                continue
            if line == "e":
                new_state = not crypto_engine.eve_active
                for d in SWARM_FLEET:
                    d.crypto.update_threat_state(new_state)
                lbl = "ACTIVE (25% QBER -> ML-KEM PQC Active)" if new_state else "CLEAR (BB84 QKD Restored)"
                print(f"\n[SECURITY SWARM] Eve Eavesdropper state changed to: {lbl}")
            elif line == "t":
                for d in SWARM_FLEET:
                    d.crypto.inject_tamper_flag = True
                print("\n[TESTBENCH SWARM] Next telemetry packets will carry 1 CORRUPTED BIT.")
            elif line == "r":
                for d in SWARM_FLEET:
                    d.crypto.inject_replay_flag = True
                print("\n[TESTBENCH SWARM] Next telemetry packets will REPLAY PREVIOUS NONCES.")
            elif line == "j":
                jam = not SWARM_FLEET[0].flight.jamming_active
                for d in SWARM_FLEET:
                    d.flight.jamming_active = jam
                print(f"\n[EW TESTBENCH] RF Electronic Jamming: {'ACTIVE (FHSS Hopping Engaging)' if jam else 'OFF (Clear Spectrum)'}")
            elif line == "s":
                for d in SWARM_FLEET:
                    d.flight.flight_mode = "SWARM_PATROL" if d.flight.flight_mode != "SWARM_PATROL" else "AUTO_MISSION"
                print("\n[NAV SWARM] Swarm formation patrol state toggled.")
            elif line == "g":
                for d in SWARM_FLEET:
                    d.flight.lat += 0.01
                print("\n[NAV SWARM] Forced UAV displacement outside Geofence -> AUTO-RTL ENGAGED.")
            elif line == "q":
                print("\n[SHUTDOWN] Exiting enclave cleanly...")
                os._exit(0)
        except (KeyboardInterrupt, EOFError):
            break


async def run_uav_client():
    await asyncio.sleep(1.0)
    ws_url = f"ws://127.0.0.1:{WS_PORT}"
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(ws_url, max_size=512 * 1024) as ws:
                backoff = 1.0
                await asyncio.gather(
                    telemetry_sender_loop(ws),
                    command_receiver_loop(ws),
                )
        except (ConnectionError, OSError, websockets.WebSocketException):
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 5.0)


async def main():
    local_ips = get_local_ip_addresses()
    print_banner(local_ips)

    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    loop = asyncio.get_running_loop()
    input_thread = threading.Thread(target=stdin_listener, args=(loop,), daemon=True)
    input_thread.start()

    asyncio.create_task(heartbeat_monitor())
    asyncio.create_task(run_uav_client())

    try:
        import vision_service
        asyncio.create_task(vision_service.connect_c2())
        import weather_integration
        asyncio.create_task(weather_integration.connect_c2())
        print("  [✓] Open-Source Integrations : YOLO Vision & OpenWeatherMap Online")
    except ImportError as e:
        print(f"  [!] Open-Source Integration warning: {e}")

    async with websockets.serve(server_handler, WS_HOST, WS_PORT, max_size=512 * 1024, ping_interval=20, ping_timeout=15):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[SYSTEM] Sovereign Enclave Stopped.")
        sys.exit(0)
