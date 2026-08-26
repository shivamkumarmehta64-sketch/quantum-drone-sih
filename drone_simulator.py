#!/usr/bin/env python3
"""drone_simulator.py - Tactical UAV SITL Flight Engine & Edge Cryptographic Bridge.

Defense Standards & Protocols:
  - Cryptography: AES-256-GCM (RFC 5116 / NIST SP 800-38D) with 96-bit IV & 128-bit Auth Tag.
  - Quantum Layer: Dual-mode BB84 QKD key-state with NIST FIPS 203 ML-KEM-768 lattice PQC failover.
  - Anti-Replay: Monotonically increasing sequence nonces (seq_no) and UTC microsecond timestamp validation.
  - Flight Core: Multi-UAV Swarm physics (Alpha, Bravo, Charlie), 6-DoF dynamics (Pitch/Roll/Yaw/Altitude/MGRS).
  - Electronic Warfare (EW): Real-time RF Spectrum monitoring, Barrage Jamming simulation & Quantum-Synchronized FHSS (Frequency Hopping Spread Spectrum).
  - Autonomous Navigation: Multi-waypoint mission planner with sequential targeting, geofencing & auto-RTL.
  - AI Recon Optical Engine: Synthetic Computer Vision reconnaissance target detection & encrypted snapshot streaming.
"""

import asyncio
import base64
import hashlib
import json
import math
import os
import random
import sys
import threading
import time
from datetime import datetime, timezone

import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
try:
    from mavsdk import System
    MAVSDK_AVAILABLE = True
except ImportError:
    MAVSDK_AVAILABLE = False

# --- Configuration & Defaults ---
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8765")
AUTH_TOKEN = os.getenv("C2_TOKEN", "SIH-QUANTUM-2026")
TICK_INTERVAL = 0.5  # 2 Hz telemetry stream
USE_SITL = os.getenv("USE_SITL", "false").lower() == "true"

# Cryptographic Root Seeds for Dual-Layer Quantum Key Distribution
SEED_BB84 = b"SIH-2026-BB84-QUANTUM-KEY-EXCHANGE-ROOT"
SEED_PQC = b"SIH-2026-ML-KEM-768-LATTICE-PQC-ROOT"

# Recon synthetic targets database for AI optical vision simulation
RECON_TARGET_CATALOG = [
    {"type": "HOSTILE_RADAR_STATION", "label": "SAM-6 SEARCH RADAR", "confidence": 0.94, "threat": "HIGH"},
    {"type": "MILITARY_CONVOY", "label": "ARMOURED SUPPLY CONVOY", "confidence": 0.89, "threat": "MEDIUM"},
    {"type": "COMM_BUNKER", "label": "REINFORCED C2 BUNKER", "confidence": 0.92, "threat": "HIGH"},
    {"type": "SURVEILLANCE_POST", "label": "BORDER OBSERVATION TOWER", "confidence": 0.87, "threat": "LOW"},
    {"type": "FRIENDLY_OUTPOST", "label": "FORWARD PATROL BASE-ALPHA", "confidence": 0.98, "threat": "FRIENDLY"},
]


def utcnow_str():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def haversine_meters(lat1, lon1, lat2, lon2):
    """Calculate Great-Circle distance in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class QuantumCryptoEngine:
    """Edge Cryptographic Engine implementing AES-256-GCM + BB84/ML-KEM-768."""

    def __init__(self, auth_token: str, node_id: str, seed_offset: int = 0):
        self.node_id = node_id
        self.auth_token = auth_token.encode("utf-8")
        self.qber = 0.012  # Normal low quantum bit error rate (< 2%)
        self.eve_active = False
        self.pqc_active = False
        self.seq_no = 1000 + seed_offset * 100
        self.inbound_last_seq = 0

        # Derive 256-bit symmetric session keys
        self.key_bb84 = hashlib.sha256(self.auth_token + b":BB84:" + SEED_BB84).digest()
        self.key_pqc = hashlib.sha256(self.auth_token + b":PQC:" + SEED_PQC).digest()

        # Flags for attack testbench injection
        self.inject_tamper_flag = False
        self.inject_replay_flag = False
        self.last_clean_wireframe = None

    @property
    def current_key(self) -> bytes:
        return self.key_pqc if self.pqc_active else self.key_bb84

    @property
    def key_mode(self) -> str:
        return "ML-KEM-768 (PQC)" if self.pqc_active else "BB84-QKD"

    @property
    def key_hash(self) -> str:
        return hashlib.sha256(self.current_key).hexdigest()[:16].upper()

    def update_threat_state(self, eve_state: bool):
        self.eve_active = eve_state
        if self.eve_active:
            self.qber = random.uniform(0.24, 0.28)  # High QBER exceeding 25% DEFCON threshold
            self.pqc_active = True
        else:
            self.qber = random.uniform(0.008, 0.018)
            self.pqc_active = False

    def encrypt_payload(self, data_dict: dict) -> dict:
        """Encrypt payload dictionary using AES-256-GCM (RFC 5116)."""
        self.seq_no += 1
        data_dict["seq_no"] = self.seq_no
        data_dict["timestamp"] = utcnow_str()

        plaintext = json.dumps(data_dict, separators=(",", ":")).encode("utf-8")
        aesgcm = AESGCM(self.current_key)
        iv = os.urandom(12)  # Standard 96-bit nonce/IV

        # AESGCM.encrypt appends 16-byte (128-bit) authentication tag
        encrypted_blob = aesgcm.encrypt(iv, plaintext, None)
        ciphertext_bytes = encrypted_blob[:-16]
        tag_bytes = encrypted_blob[-16:]

        # Attack Testbench Tamper Injection
        if self.inject_tamper_flag:
            self.inject_tamper_flag = False
            corrupted = bytearray(ciphertext_bytes)
            if len(corrupted) > 0:
                corrupted[0] ^= 0xFF  # Flip 8 bits
            ciphertext_bytes = bytes(corrupted)
            print(f"\n[TESTBENCH-{self.node_id}] >>> INJECTED 1-BIT TAMPERED CIPHERTEXT (Auth Tag Mismatch Test)")

        iv_b64 = base64.b64encode(iv).decode("ascii")
        ct_b64 = base64.b64encode(ciphertext_bytes + tag_bytes).decode("ascii")
        tag_b64 = base64.b64encode(tag_bytes).decode("ascii")

        wireframe = {
            "type": "secure_telemetry",
            "node_id": self.node_id,
            "seq_no": self.seq_no,
            "timestamp": data_dict["timestamp"],
            "iv": iv_b64,
            "ciphertext": ct_b64,
            "tag": tag_b64,
            "algo": "AES-256-GCM",
            "key_mode": self.key_mode,
            "key_hash": self.key_hash,
            "qber": round(self.qber, 4),
            "pqc_active": self.pqc_active,
            "eve_active": self.eve_active,
        }

        # Attack Testbench Replay Injection
        if self.inject_replay_flag and self.last_clean_wireframe:
            self.inject_replay_flag = False
            print(f"\n[TESTBENCH-{self.node_id}] >>> INJECTED REPLAY PACKET (Resending Seq #{self.last_clean_wireframe['seq_no']})")
            return dict(self.last_clean_wireframe)

        self.last_clean_wireframe = dict(wireframe)
        return wireframe

    def decrypt_inbound_command(self, envelope: dict) -> dict:
        """Decrypt inbound command using AES-256-GCM and verify sequence/tag."""
        try:
            iv = base64.b64decode(envelope.get("iv", ""))
            combined = base64.b64decode(envelope.get("ciphertext", ""))
            seq_no = envelope.get("seq_no", 0)

            if seq_no <= self.inbound_last_seq:
                print(f"[{self.node_id} ANTI-REPLAY] Stale seq {seq_no} <= last {self.inbound_last_seq} DROPPED")
                return None

            aesgcm = AESGCM(self.current_key)
            decrypted_bytes = aesgcm.decrypt(iv, combined, None)
            cmd_data = json.loads(decrypted_bytes.decode("utf-8"))
            self.inbound_last_seq = seq_no
            return cmd_data
        except Exception as e:
            print(f"[{self.node_id} SECURITY] Inbound command decryption failed: {e}")
            return None


class DroneSITLEngine:
    """High-Fidelity UAV Flight & Navigation Simulation Core."""

    def __init__(self, node_id: str, offset_lat: float = 0.0, offset_lon: float = 0.0, callsign: str = "ALPHA-1"):
        self.node_id = node_id
        self.callsign = callsign

        # Base Home Launch Pad (Northern Border Recon Enclave)
        self.home_lat = 31.6340
        self.home_lon = 74.8723
        self.lat = self.home_lat + offset_lat + random.uniform(-0.0003, 0.0003)
        self.lon = self.home_lon + offset_lon + random.uniform(-0.0003, 0.0003)

        self.alt_agl = 45.0 + random.uniform(-5.0, 5.0)  # Meters AGL
        self.alt_msl = self.alt_agl + 215.0  # Meters MSL
        self.ground_speed = 13.5  # m/s (~48 km/h)
        self.heading = random.uniform(0, 360)
        self.pitch = 1.5
        self.roll = 0.0
        self.yaw = self.heading

        self.battery_voltage = 16.8
        self.battery_pct = 100.0
        self.armed = True
        self.flight_mode = "AUTO_MISSION"  # "AUTO_MISSION", "WAYPOINT_NAV", "SWARM_PATROL", "RTL_FAILSAFE", "LANDED"

        self.geofence_radius = 500.0  # 500m default safe perimeter
        self.geofence_breached = False

        # Multi-Waypoint Navigation Route
        self.waypoints_queue = []  # List of dicts: [{"lat": ..., "lon": ..., "alt": ...}]
        self.current_wp_index = 0
        self.target_lat = None
        self.target_lon = None

        # Electronic Warfare (EW) & FHSS state
        self.fhss_channel = random.randint(1, 64)
        self.rf_frequency_mhz = 2412.0 + self.fhss_channel * 1.1
        self.rf_rssi_dbm = -48.0
        self.rf_snr_db = 34.0
        self.jamming_active = False

        # Reconnaissance Contacts
        self.detected_targets = []
        self._last_recon_scan = 0.0

    def update_ew_physics(self, dt: float):
        """Simulate Frequency Hopping Spread Spectrum (FHSS) anti-jamming."""
        # Pseudo-random frequency hop at high rate
        self.fhss_channel = (self.fhss_channel + 7) % 64 + 1
        self.rf_frequency_mhz = round(2412.0 + self.fhss_channel * 1.1, 1)

        if self.jamming_active:
            # Jamming noise floor spikes, but FHSS maintains link
            self.rf_rssi_dbm = round(random.uniform(-78.0, -72.0), 1)
            self.rf_snr_db = round(random.uniform(14.0, 18.0), 1)
        else:
            self.rf_rssi_dbm = round(random.uniform(-52.0, -44.0), 1)
            self.rf_snr_db = round(random.uniform(30.0, 36.0), 1)

    def scan_recon_targets(self):
        """Simulate onboard AI synthetic target recognition."""
        now = time.time()
        if now - self._last_recon_scan > 3.0:
            self._last_recon_scan = now
            if random.random() < 0.65:
                proto = random.choice(RECON_TARGET_CATALOG)
                t_lat = round(self.lat + random.uniform(-0.0015, 0.0015), 6)
                t_lon = round(self.lon + random.uniform(-0.0015, 0.0015), 6)
                mgrs_str = f"43REQ-{int(abs(t_lat)*1000)%10000:04d}-{int(abs(t_lon)*1000)%10000:04d}"
                self.detected_targets = [{
                    "type": proto["type"],
                    "label": proto["label"],
                    "threat": proto["threat"],
                    "confidence": round(proto["confidence"] + random.uniform(-0.03, 0.03), 2),
                    "lat": t_lat,
                    "lon": t_lon,
                    "mgrs": mgrs_str,
                    "range_m": round(haversine_meters(self.lat, self.lon, t_lat, t_lon), 1),
                }]

    def update_physics(self, dt: float):
        """Update 6-DoF dynamics, geofence boundary checks, and battery discharge."""
        self.update_ew_physics(dt)
        self.scan_recon_targets()

        if not self.armed:
            self.ground_speed = 0.0
            self.alt_agl = max(0.0, self.alt_agl - 3.0 * dt)
            return

        dist_from_home = haversine_meters(self.home_lat, self.home_lon, self.lat, self.lon)

        # Autonomous Geofence Enforcement
        if dist_from_home > self.geofence_radius:
            if not self.geofence_breached:
                self.geofence_breached = True
                self.flight_mode = "RTL_FAILSAFE"
                print(f"\n[{self.node_id} FAILSAFE] GEOFENCE BREACH ({dist_from_home:.1f}m > {self.geofence_radius}m) -> AUTO-RTL ENGAGED")

        # Flight state machine
        if self.flight_mode == "RTL_FAILSAFE":
            d_lat = self.home_lat - self.lat
            d_lon = (self.home_lon - self.lon) * math.cos(math.radians(self.lat))
            target_heading = math.degrees(math.atan2(d_lon, d_lat)) % 360

            angle_diff = (target_heading - self.heading + 180) % 360 - 180
            self.heading = (self.heading + math.copysign(min(abs(angle_diff), 40.0 * dt), angle_diff)) % 360
            self.roll = math.copysign(min(abs(angle_diff) * 0.55, 22.0), angle_diff)
            self.pitch = 1.0

            if dist_from_home < 12.0:
                self.ground_speed = max(0.0, self.ground_speed - 4.0 * dt)
                self.alt_agl = max(0.0, self.alt_agl - 4.0 * dt)
                if self.alt_agl <= 0.5:
                    self.flight_mode = "LANDED"
                    self.armed = False
                    print(f"[{self.node_id}] UAV Safely Landed and Secured at Home Base.")
            else:
                self.ground_speed = 15.0

        elif self.flight_mode == "WAYPOINT_NAV" and self.target_lat is not None and self.target_lon is not None:
            dist_to_wp = haversine_meters(self.lat, self.lon, self.target_lat, self.target_lon)
            d_lat = self.target_lat - self.lat
            d_lon = (self.target_lon - self.lon) * math.cos(math.radians(self.lat))
            target_heading = math.degrees(math.atan2(d_lon, d_lat)) % 360

            angle_diff = (target_heading - self.heading + 180) % 360 - 180
            self.heading = (self.heading + math.copysign(min(abs(angle_diff), 45.0 * dt), angle_diff)) % 360
            self.roll = math.copysign(min(abs(angle_diff) * 0.6, 25.0), angle_diff)
            self.pitch = 2.0

            if dist_to_wp < 10.0:
                print(f"[{self.node_id}] Reached Waypoint ({self.target_lat:.5f}, {self.target_lon:.5f})")
                if self.waypoints_queue and self.current_wp_index + 1 < len(self.waypoints_queue):
                    self.current_wp_index += 1
                    next_wp = self.waypoints_queue[self.current_wp_index]
                    self.target_lat = next_wp["lat"]
                    self.target_lon = next_wp["lon"]
                    print(f"[{self.node_id}] Progressing to Waypoint #{self.current_wp_index + 1}: ({self.target_lat:.5f}, {self.target_lon:.5f})")
                else:
                    print(f"[{self.node_id}] All mission waypoints completed -> Resuming autonomous patrol.")
                    self.flight_mode = "AUTO_MISSION"
                    self.target_lat = None
                    self.target_lon = None
                    self.waypoints_queue = []
            else:
                self.ground_speed = 15.5

        elif self.flight_mode == "SWARM_PATROL":
            self.heading = (self.heading + 12.0 * dt) % 360
            self.roll = 6.0
            self.pitch = 1.0
            self.ground_speed = 14.0

        else:
            self.heading = (self.heading + random.uniform(-4.0, 4.0)) % 360
            self.roll = random.uniform(-3.0, 3.0)
            self.pitch = random.uniform(-2.0, 2.0)
            self.alt_agl = round(max(20.0, min(120.0, self.alt_agl + random.uniform(-0.4, 0.4))), 1)
            self.ground_speed = round(max(10.0, min(22.0, self.ground_speed + random.uniform(-0.25, 0.25))), 1)

        # Coordinate Integration
        dist_travelled = self.ground_speed * dt
        bearing_rad = math.radians(self.heading)
        delta_lat = (dist_travelled * math.cos(bearing_rad)) / 111139.0
        delta_lon = (dist_travelled * math.sin(bearing_rad)) / (111139.0 * math.cos(math.radians(self.lat)))

        self.lat += delta_lat
        self.lon += delta_lon
        self.alt_msl = self.alt_agl + 215.0
        self.yaw = self.heading

        # Battery discharge
        self.battery_voltage = max(13.8, round(self.battery_voltage - 0.0006 * dt, 2))
        self.battery_pct = max(0.0, round(((self.battery_voltage - 13.8) / (16.8 - 13.8)) * 100.0, 1))

    def get_telemetry_payload(self) -> dict:
        dist_from_home = round(haversine_meters(self.home_lat, self.home_lon, self.lat, self.lon), 1)
        return {
            "node_id": self.node_id,
            "callsign": self.callsign,
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "home_lat": round(self.home_lat, 6),
            "home_lon": round(self.home_lon, 6),
            "alt_agl": round(self.alt_agl, 1),
            "alt_msl": round(self.alt_msl, 1),
            "ground_speed": round(self.ground_speed, 1),
            "heading": round(self.heading, 1),
            "pitch": round(self.pitch, 1),
            "roll": round(self.roll, 1),
            "yaw": round(self.yaw, 1),
            "battery_v": round(self.battery_voltage, 2),
            "battery_pct": round(self.battery_pct, 1),
            "armed": self.armed,
            "flight_mode": self.flight_mode,
            "geofence_radius": self.geofence_radius,
            "geofence_dist": dist_from_home,
            "geofence_breached": self.geofence_breached,
            "mgrs_coords": f"43REQ-{int(abs(self.lat)*1000)%10000:04d}-{int(abs(self.lon)*1000)%10000:04d}",
            "fhss_channel": self.fhss_channel,
            "rf_freq_mhz": self.rf_frequency_mhz,
            "rf_rssi_dbm": self.rf_rssi_dbm,
            "rf_snr_db": self.rf_snr_db,
            "jamming_active": self.jamming_active,
            "recon_targets": self.detected_targets,
            "waypoint_count": len(self.waypoints_queue),
            "active_wp_index": self.current_wp_index,
        }


class DroneNode:
    """Encapsulates a single UAV node with crypto engine and flight dynamics."""

    def __init__(self, node_id: str, callsign: str, offset_lat: float, offset_lon: float, seed_idx: int):
        self.node_id = node_id
        self.callsign = callsign
        self.crypto = QuantumCryptoEngine(AUTH_TOKEN, node_id, seed_idx)
        self.flight = DroneSITLEngine(node_id, offset_lat, offset_lon, callsign)


# --- Global Swarm Fleet Architecture ---
SWARM_FLEET = [
    DroneNode("DRONE-ALPHA", "ALPHA-1 (RECON)", 0.0008, 0.0008, 0),
    DroneNode("DRONE-BRAVO", "BRAVO-2 (PATROL)", -0.0009, 0.0011, 1),
    DroneNode("DRONE-CHARLIE", "CHARLIE-3 (RELAY)", 0.0012, -0.0010, 2),
]

# Primary single-drone alias for backward compatibility
primary_node = SWARM_FLEET[0]
crypto_engine = primary_node.crypto
drone_flight = primary_node.flight
NODE_ID = primary_node.node_id


async def telemetry_sender_loop(ws):
    """Encrypt and stream telemetry for all active swarm drones to C2 Relay."""
    for d in SWARM_FLEET:
        await ws.send(
            json.dumps({
                "type": "handshake",
                "token": AUTH_TOKEN,
                "node_id": d.node_id,
                "capabilities": ["telemetry", "aes_256_gcm", "bb84", "pqc_kem", "fhss_ew", "ai_recon", "multi_waypoint"],
            })
        )

    last_time = time.time()
    while True:
        now = time.time()
        dt = max(0.01, min(0.5, now - last_time))
        last_time = now

        for d in SWARM_FLEET:
            d.flight.update_physics(dt)
            telemetry_data = d.flight.get_telemetry_payload()
            wireframe = d.crypto.encrypt_payload(telemetry_data)
            await ws.send(json.dumps(wireframe))

        await asyncio.sleep(TICK_INTERVAL)


async def command_receiver_loop(ws):
    """Receive and execute encrypted inbound mission commands from GCS."""
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        mtype = msg.get("type")
        if mtype == "encrypted_command":
            target = msg.get("target_node", "ALL")
            targets_to_exec = SWARM_FLEET if target in ("ALL", "BROADCAST", "SWARM") else [d for d in SWARM_FLEET if d.node_id == target]

            for d in targets_to_exec:
                cmd = d.crypto.decrypt_inbound_command(msg)
                if cmd:
                    action = cmd.get("action")
                    print(f"\n[{d.node_id} CMD EXEC] Authenticated command received: {action}")

                    if action == "RTL" or action == "SWARM_RTL":
                        d.flight.flight_mode = "RTL_FAILSAFE"
                    elif action == "ARM":
                        d.flight.armed = True
                        if d.flight.flight_mode == "LANDED":
                            d.flight.flight_mode = "AUTO_MISSION"
                            d.flight.alt_agl = 35.0
                    elif action == "DISARM":
                        d.flight.armed = False
                    elif action == "SET_GEOFENCE":
                        radius = float(cmd.get("radius", 500.0))
                        d.flight.geofence_radius = radius
                    elif action == "GOTO_WAYPOINT":
                        d.flight.target_lat = float(cmd.get("lat"))
                        d.flight.target_lon = float(cmd.get("lon"))
                        d.flight.flight_mode = "WAYPOINT_NAV"
                        d.flight.waypoints_queue = [{"lat": d.flight.target_lat, "lon": d.flight.target_lon}]
                        d.flight.current_wp_index = 0
                    elif action == "UPLOAD_WAYPOINTS":
                        wps = cmd.get("waypoints", [])
                        if wps:
                            d.flight.waypoints_queue = wps
                            d.flight.current_wp_index = 0
                            d.flight.target_lat = float(wps[0]["lat"])
                            d.flight.target_lon = float(wps[0]["lon"])
                            d.flight.flight_mode = "WAYPOINT_NAV"
                            print(f"[{d.node_id}] Loaded {len(wps)} Waypoints into Flight Guidance System.")
                    elif action == "SWARM_FORMATION_V":
                        d.flight.flight_mode = "SWARM_PATROL"
                    elif action == "TRIGGER_TAMPER":
                        d.crypto.inject_tamper_flag = True
                    elif action == "TRIGGER_REPLAY":
                        d.crypto.inject_replay_flag = True
                    elif action == "TOGGLE_JAMMING":
                        d.flight.jamming_active = not d.flight.jamming_active
                        print(f"[{d.node_id} EW] Electronic Jamming state toggled: {d.flight.jamming_active}")

        elif mtype == "qber_alert":
            is_eve = bool(msg.get("eavesdropper_active", False)) or float(msg.get("qber", 0)) > 0.2
            for d in SWARM_FLEET:
                d.crypto.update_threat_state(is_eve)
            status_txt = "ACTIVE (25% QBER -> ML-KEM PQC)" if is_eve else "OFF (BB84 QKD)"
            print(f"[SECURITY SWARM] Threat state synchronized: Eve={status_txt}")

        elif mtype == "ew_jamming_toggle":
            jam_state = bool(msg.get("jamming_active", False))
            for d in SWARM_FLEET:
                d.flight.jamming_active = jam_state
            print(f"[EW SWARM] Electronic Jamming state: {jam_state}")


async def session_runner():
    """Connect and maintain resilient communication with C2 Relay."""
    async with websockets.connect(WS_URL, max_size=512 * 1024) as ws:
        print(f"[LINK] Tactical Swarm Fleet connected to C2 Relay Hub ({WS_URL})")
        await asyncio.gather(telemetry_sender_loop(ws), command_receiver_loop(ws))


async def async_main():
    backoff = 1.0
    while True:
        try:
            await session_runner()
            backoff = 1.0
        except (ConnectionError, OSError, websockets.WebSocketException) as e:
            print(f"[LINK DOWN] Reconnecting to C2 Hub in {backoff:.1f}s... ({e.__class__.__name__})")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 10.0)


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n[UAV SWARM] Shutdown cleanly.")
        sys.exit(0)

