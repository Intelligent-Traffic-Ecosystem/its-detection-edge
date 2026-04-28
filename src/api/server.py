import os
import logging
import socket
import uvicorn
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter

app = FastAPI()

# Add prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

DETECTION_COUNT = Counter('detections_total', 'Total number of vehicle detections')

@app.get("/health")
def health_check():
    return {"status": "healthy"}

def start_api_server():
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
