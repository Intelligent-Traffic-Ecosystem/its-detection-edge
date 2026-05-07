import os
import logging
import socket
import json
import uvicorn
import cv2
from fastapi import FastAPI, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from prometheus_client import make_asgi_app, Counter, Gauge

app = FastAPI()
camera_stream = None  # Global reference to be set at startup

# Prometheus metrics
DETECTION_COUNT = Counter('detections_total', 'Total number of vehicle detections')
INFERENCE_LATENCY = Gauge('inference_latency_ms', 'Time taken for YOLO inference in milliseconds')
CPU_TEMP = Gauge('cpu_temperature_celsius', 'Current CPU temperature of the Raspberry Pi')
MEMORY_USAGE = Gauge('memory_usage_percent', 'Current memory usage percentage')

@app.get("/")
def root_redirect():
    return RedirectResponse(url="/calibrate")

# Add prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.get("/health")
def health_check():
    # Update hardware metrics on every health check
    _update_hardware_metrics()
    return {
        "status": "healthy",
        "cpu_temp": CPU_TEMP._value.get(),
        "memory": MEMORY_USAGE._value.get()
    }

def _update_hardware_metrics():
    try:
        # Read CPU Temperature (Linux/Pi standard path)
        if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = float(f.read()) / 1000.0
                CPU_TEMP.set(temp)
        
        # Memory usage (simplified for demo/local)
        import psutil
        MEMORY_USAGE.set(psutil.virtual_memory().percent)
    except Exception as e:
        logging.warning("Failed to update hardware metrics: %s", e)

@app.get("/snapshot")
def get_snapshot():
    if camera_stream is None:
        raise HTTPException(status_code=503, detail="Camera stream not initialized")
    
    frame = camera_stream.get_frame()
    if frame is None:
        raise HTTPException(status_code=404, detail="No frame captured yet")
    
    # Encode to JPEG
    success, encoded_image = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode image")
    
    return Response(content=encoded_image.tobytes(), media_type="image/jpeg")

@app.post("/config/lanes")
async def save_lanes(config: dict):
    try:
        config_path = "config/lanes.json"
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        logging.info("Updated lane configuration via API")
        return {"status": "success", "message": "Configuration saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/calibrate", response_class=HTMLResponse)
def get_calibrate_ui():
    html_path = os.path.join(os.path.dirname(__file__), "static/calibrate.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Calibration UI not found")
    with open(html_path, "r") as f:
        return f.read()

def start_api_server(stream=None):
    global camera_stream
    camera_stream = stream
    port = int(os.getenv("API_PORT", 8001))
    port = _find_available_port("0.0.0.0", port)
    if port != int(os.getenv("API_PORT", 8001)):
        logging.warning("API port %s is in use; using %s instead.", os.getenv("API_PORT", 8001), port)

    logging.info("API server listening on http://localhost:%s", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def _is_port_available(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _find_available_port(host, preferred_port, max_attempts=20):
    for offset in range(max_attempts):
        port = preferred_port + offset
        if _is_port_available(host, port):
            return port

    raise RuntimeError(f"No available API port found from {preferred_port} to {preferred_port + max_attempts - 1}")
