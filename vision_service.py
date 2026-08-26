import cv2
import numpy as np
import websockets
import asyncio
import json
import base64
import os

# Dummy YOLO processing since loading a real YOLO model requires weights.
# We will simulate YOLO inference.
async def process_frame(frame_b64):
    try:
        header, encoded = frame_b64.split(",", 1)
        data = base64.b64decode(encoded)
        np_arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        # Simulate ML Detection (YOLO)
        height, width = img.shape[:2]
        
        # Draw a simulated bounding box
        start_point = (int(width*0.2), int(height*0.2))
        end_point = (int(width*0.8), int(height*0.8))
        color = (0, 255, 0)
        thickness = 2
        img = cv2.rectangle(img, start_point, end_point, color, thickness)
        cv2.putText(img, 'YOLO: Threat Detected (95%)', (start_point[0], start_point[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        
        # Re-encode to base64
        _, buffer = cv2.imencode('.jpg', img)
        processed_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')
        
        return {
            "bounding_boxes": [{"label": "Threat", "confidence": 0.95, "x1": 0.2, "y1": 0.2, "x2": 0.8, "y2": 0.8}],
            "processed_frame": processed_b64
        }
    except Exception as e:
        print(f"[YOLO Error] {e}")
        return None

async def connect_c2():
    uri = "ws://127.0.0.1:8765"
    async with websockets.connect(uri) as ws:
        # Handshake
        await ws.send(json.dumps({
            "type": "handshake",
            "token": os.getenv("C2_TOKEN", "SIH-QUANTUM-2026"),
            "node_id": "YOLO-VISION",
            "capabilities": ["ai_recon"]
        }))
        
        print("[VISION] Connected to C2 Relay.")
        async for message in ws:
            try:
                data = json.loads(message)
                if data.get("type") == "snapshot_broadcast":
                    snapshot = data.get("snapshot")
                    if snapshot:
                        print("[VISION] Received frame for YOLO processing...")
                        result = await process_frame(snapshot)
                        if result:
                            # Send back detection result
                            await ws.send(json.dumps({
                                "type": "ai_detection_alert",
                                "node_id": "YOLO-VISION",
                                "source_node": data.get("from_node"),
                                "detections": result["bounding_boxes"],
                                "processed_snapshot": result["processed_frame"]
                            }))
            except json.JSONDecodeError:
                pass

if __name__ == "__main__":
    print("[VISION] Starting Open-Source YOLO service...")
    try:
        asyncio.run(connect_c2())
    except KeyboardInterrupt:
        print("\n[VISION] Shutdown cleanly.")
