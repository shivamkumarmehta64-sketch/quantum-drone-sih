@echo off
title QUANTUM DRONE GCS - SOVEREIGN MASTER CONSOLE
color 0B
cls
echo.
echo  ========================================================================
echo   SOVEREIGN AIR-GAPPED QUANTUM-RESILIENT DRONE TELEMETRY & C2 ENCLAVE
echo   Smart India Hackathon / Defence Enclave Architecture
echo  ========================================================================
echo.
echo  [1/2] Opening Tactical GCS Dashboard in browser...
start "" http://localhost:8000/index.html

echo  [2/2] Starting Unified Master Backend on Windows & Physical Wi-Fi...
echo.
echo  ========================================================================
echo   KEEP THIS WINDOW OPEN WHILE USING THE SYSTEM.
echo   * Tactical Dashboard : http://localhost:8000/index.html
echo   * Phone Hotspot Link : http://192.168.137.1:8000/phone_client.html
echo   * Phone Wi-Fi Link   : http://10.237.210.14:8000/phone_client.html
echo.
echo   Interactive Keyboard Controls:
echo     [E] Toggle Eve Eavesdropper (25%% QBER -^> ML-KEM PQC Key Rotation)
echo     [T] Inject 1-Bit Corrupted Ciphertext (Auth Tag Mismatch Test)
echo     [R] Inject Replay Packet (Stale Nonce Drop Test)
echo     [J] Toggle EW RF Jammer (FHSS Frequency Hopping Test)
echo     [S] Toggle Swarm Formation Patrol
echo     [G] Simulate Geofence Breach (Trigger Auto-RTL)
echo     [Q] Graceful Shutdown
echo  ========================================================================
echo.

cd /d "%~dp0"
python unified_runner.py 2>nul || wsl.exe -d Ubuntu-26.04 --cd /home/shiva/quantum-drone-sih python3 unified_runner.py

pause
