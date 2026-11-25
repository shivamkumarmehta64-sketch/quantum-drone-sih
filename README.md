# Hybrid Quantum-Resilient Drone Surveillance System (SIH)

> **Secure, Tamper-Proof Cryptographic Telemetry & Command Link (C2) for Unmanned Aerial Vehicles (UAVs) with Real-Time Ground Station Monitoring**

Built to align with **MoD / DRDO / DGCA** architecture standards, **NIST SP 800-38D (AES-256-GCM)**, and **NIST FIPS 203 (ML-KEM-768)** post-quantum cryptography in a zero-internet, air-gapped Wi-Fi enclave.

---

## Core Architecture & Capabilities

- **Edge Cryptographic Engine:** Hardware-accelerated AES-256-GCM (96-bit IV + 128-bit auth tag) paired with BB84 QKD simulation and automated NIST FIPS 203 ML-KEM-768 lattice post-quantum fallback.
- **Anti-Replay & Integrity:** Monotonic sequence nonces (`seq_no`) and UTC microsecond timestamp verification rejecting stale or replayed packets.
- **Multi-UAV Swarm Fleet Simulation:** Real-time telemetry streaming for `DRONE-ALPHA`, `DRONE-BRAVO`, `DRONE-CHARLIE`, and mobile PWA field nodes with 6-DoF flight dynamics and emergency RTL.
- **Air-Gapped Ground Control Station (GCS):** Browser-based tactical GCS (`index.html`, `phone_client.html`) backed by `unified_runner.py`, `drone_simulator.py`, and `vision_service.py`.

## Quick Start

1. Run `QuantumDroneGCS.bat` (Windows) or `python unified_runner.py`.
2. See [`README_AIRGAPPED.md`](./README_AIRGAPPED.md) for the complete air-gapped deployment specification and testbench documentation.

## License

MIT License — see [`LICENSE`](./LICENSE).