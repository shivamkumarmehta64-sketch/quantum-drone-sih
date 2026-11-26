# Hybrid Quantum-Resilient Drone Surveillance System (`quantum-drone-sih`)

> **Secure, Tamper-Proof Cryptographic Telemetry & Command Link (C2) for Unmanned Aerial Vehicles (UAVs) with Real-Time Ground Station Monitoring.**

Built to align with **MoD / DRDO / DGCA** architecture standards, **NIST SP 800-38D (AES-256-GCM)**, and **NIST FIPS 203 (ML-KEM-768)** post-quantum cryptography in a zero-internet, air-gapped Wi-Fi enclave.

**Live GCS Preview:** **[quantum-drone-gcs.pages.dev](https://quantum-drone-gcs.pages.dev)**

---

## Core Architecture & Capabilities

- **Edge Cryptographic Engine:** Hardware-accelerated AES-256-GCM (96-bit IV + 128-bit auth tag) and ChaCha20-Poly1305 AEAD paired with BB84 QKD simulation and automated NIST FIPS 203 ML-KEM-768 lattice post-quantum fallback.
- **Anti-Replay & Integrity:** Monotonic sequence nonces (`seq_no`) and UTC microsecond timestamp verification rejecting stale, replayed, or bit-tampered packets.
- **Multi-UAV Swarm Fleet Simulation:** Real-time telemetry streaming for `DRONE-ALPHA`, `DRONE-BRAVO`, `DRONE-CHARLIE`, and mobile PWA field nodes (`phone_client.html`) with 6-DoF flight dynamics and emergency Return-to-Launch (RTL).
- **Air-Gapped Ground Control Station (GCS):** Browser-based tactical GCS (`index.html`, `style.css`) backed by `unified_runner.py`, `server.py`, `drone_simulator.py`, `vision_service.py`, and `weather_integration.py`.

---

## Repository Layout

| File / Directory | Purpose |
| :--- | :--- |
| `unified_runner.py` / `QuantumDroneGCS.bat` | One-click launcher for the GCS server, drone simulator, and telemetry loop |
| `server.py` | Air-gapped telemetry & WebSocket/HTTP ground station backend |
| `drone_simulator.py` | 6-DoF multi-UAV flight dynamics & encrypted packet emitter |
| `vision_service.py` / `weather_integration.py` | Tactical optical feed & local weather telemetry integration |
| `index.html` / `phone_client.html` | Tactical GCS dashboard and mobile PWA field node |
| `testbench/` | AEAD latency profiler (`benchmark_crypto.py`), replay (`inject_replay.py`), and tamper (`inject_tamper.py`) injectors |

---

## Quick Start & Verification

### 1. Run the Air-Gapped GCS

```bash
# Windows
QuantumDroneGCS.bat

# Cross-platform
python unified_runner.py
```

See [`README_AIRGAPPED.md`](./README_AIRGAPPED.md) for the complete air-gapped deployment specification.

### 2. Run Cryptographic Testbench

```bash
pip install cryptography
python testbench/benchmark_crypto.py
```

---

## License

MIT License — see [`LICENSE`](./LICENSE).
