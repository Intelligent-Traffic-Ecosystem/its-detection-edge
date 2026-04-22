import os
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
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
