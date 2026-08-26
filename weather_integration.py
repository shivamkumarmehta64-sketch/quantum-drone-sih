import requests
import asyncio
import json
import websockets
import os

API_KEY = os.getenv("OWM_API_KEY", "dummy_api_key_for_demo")

def get_weather(lat, lon):
    if API_KEY == "dummy_api_key_for_demo":
        # Simulate weather if no API key is provided
        return {
            "temp": 25.5,
            "humidity": 60,
            "wind_speed": 4.5,
            "description": "clear sky"
        }
    
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        return {
            "temp": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "description": data["weather"][0]["description"]
        }
    except Exception as e:
        print(f"[WEATHER] Error fetching data: {e}")
        return None

async def connect_c2():
    uri = "ws://127.0.0.1:8765"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "type": "handshake",
            "token": os.getenv("C2_TOKEN", "SIH-QUANTUM-2026"),
            "node_id": "WEATHER-SERVICE",
            "capabilities": ["weather_api"]
        }))
        
        print("[WEATHER] Connected to C2 Relay.")
        
        # Keep track of last checked coords to avoid spamming the API
        last_lat = 0
        last_lon = 0
        
        async for message in ws:
            try:
                data = json.loads(message)
                # Listen to telemetry to get coordinates
                if data.get("type") == "secure_telemetry_broadcast":
                    wireframe = data.get("wireframe", {})
                    lat = wireframe.get("lat")
                    lon = wireframe.get("lon")
                    
                    if lat and lon:
                        # Only fetch if we moved significantly (e.g., >0.01 deg)
                        if abs(lat - last_lat) > 0.01 or abs(lon - last_lon) > 0.01:
                            print(f"[WEATHER] Fetching weather for {lat}, {lon}")
                            weather = get_weather(lat, lon)
                            if weather:
                                await ws.send(json.dumps({
                                    "type": "weather_update",
                                    "node_id": "WEATHER-SERVICE",
                                    "weather": weather
                                }))
                                last_lat = lat
                                last_lon = lon
            except json.JSONDecodeError:
                pass

if __name__ == "__main__":
    print("[WEATHER] Starting OpenWeatherMap integration service...")
    try:
        asyncio.run(connect_c2())
    except KeyboardInterrupt:
        print("\n[WEATHER] Shutdown cleanly.")
