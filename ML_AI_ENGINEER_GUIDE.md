# ML / AI Engineer Guide: Detection, Tracking, Kafka & Buffer

This guide covers the ML-side implementation for the Intelligent Traffic System edge service. This module receives a video feed, detects and tracks traffic objects, estimates speed/lane metadata, visualizes results, and sends or buffers events for the rest of the system.

## Role Scope

The ML / AI engineer owns:

- Video input handling from file, USB camera, or RTSP stream.
- YOLO-based vehicle detection.
- ByteTrack-based object tracking and stable vehicle IDs.
- Traffic-object filtering.
- Frame skipping for edge performance.
- Speed estimation from tracked object movement.
- Lane mapping using calibrated polygons.
- Visual output with green bounding boxes, ID, and speed.
- Kafka event publishing.
- SQLite offline buffering when Kafka is unavailable.
- Testing and demo verification for the detection pipeline.

## Pipeline Flow

```text
Video feed
  -> OpenCV frame capture
  -> YOLO detection
  -> ByteTrack tracking
  -> Lane mapping
  -> Speed estimation
  -> Event JSON creation
  -> Kafka producer
       -> Kafka topic if broker is available
       -> SQLite offline buffer if Kafka is disabled/unavailable
  -> Optional OpenCV display window
```

## Main Files

- `src/main.py`: Main end-to-end pipeline.
- `src/ml/detector.py`: YOLO model loading, detection, ByteTrack tracking, class filtering, frame skipping.
- `src/capture/camera.py`: Video/camera capture using OpenCV.
- `src/analytics/speed.py`: Pixel-distance speed estimation.
- `src/analytics/enricher.py`: Lane polygon mapping.
- `src/transport/kafka_producer.py`: Kafka sending and reconnect handling.
- `src/transport/offline_buffer.py`: SQLite offline event buffer.
- `src/api/server.py`: Health check and Prometheus metrics API.
- `config/lanes.json`: Lane polygon configuration.
- `scripts/calibrate.py`: OpenCV lane polygon calibration helper.
- `tests/test_detector.py`: Detector output tests.
- `tests/test_offline_buffer.py`: SQLite buffer tests.

## Environment Config

Runtime config is read from `.env`.

```env
CAMERA_ID=cam_01
CAMERA_URL=tests/test.mp4
STATUS_INTERVAL_SECONDS=5
LOG_DETECTIONS=false
DISPLAY_VIDEO=true

MODEL_PATH=yolov8n.pt
DETECTION_CONFIDENCE=0.4
TRACKER_CONFIG=bytetrack.yaml
FRAME_SKIP=0

KAFKA_ENABLED=false
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=traffic.events.raw

API_PORT=8001
```

## Video Input

Change the input video or camera using `CAMERA_URL` in `.env`.

Examples:

```env
CAMERA_URL=tests/test.mp4
CAMERA_URL=C:\Users\MSI\Downloads\traffic_video.mp4
CAMERA_URL=0
CAMERA_URL=rtsp://camera-ip/stream
```

Use a local video file for demos. Use RTSP or USB camera input for live deployment.

## Detection And Tracking

`TrafficDetector` uses Ultralytics YOLO and ByteTrack:

- Model: `yolov8n.pt` by default.
- Confidence threshold: controlled by `DETECTION_CONFIDENCE`.
- Tracker config: `bytetrack.yaml`.
- Allowed object classes: `car`, `motorcycle`, `bus`, `truck`, `person`, `bicycle`.
- Output includes stable `vehicle_id`, class, confidence, bbox, centroid, and frame ID.

The detector returns objects like:

```python
{
    "id": 12,
    "vehicle_id": "veh_12",
    "class": "car",
    "confidence": 0.83,
    "bbox": [100.0, 120.0, 180.0, 210.0],
    "bbox_xywh": {"x": 100.0, "y": 120.0, "w": 80.0, "h": 90.0},
    "centroid": {"x": 140.0, "y": 165.0},
    "frame_id": 42
}
```

## Speed Estimation

Speed is calculated in `src/analytics/speed.py`.

The current method:

- Tracks the bottom-center point of each bounding box.
- Stores recent positions per track ID.
- Calculates pixel movement over time.
- Converts pixels to meters using `pixels_to_meters`.
- Returns speed in km/h.

Important: speed is an estimate. For accurate real-world speed, calibrate `pixels_to_meters` for the actual camera angle and road distance.

## Lane Mapping

Lane mapping is done by `src/analytics/enricher.py`.

The code uses:

- Bottom-center point of the bbox.
- Lane polygons from `config/lanes.json`.
- Point-in-polygon logic.

If the output shows:

```text
lane=unknown
```

it means the lane polygons do not match the current video. Calibrate them:

```bash
python scripts/calibrate.py --source tests/test.mp4 --output config/lanes.json
```

Controls:

- Left click: add polygon point.
- `n`: save current polygon as the next lane.
- `u`: undo last point.
- `s`: save JSON.
- `q`: quit.

## Visualization

Enable popup visualization in `.env`:

```env
DISPLAY_VIDEO=true
```

The app opens an OpenCV window and draws:

- Green bounding box.
- Vehicle ID.
- Estimated speed.

Example label:

```text
veh_12 34.5 km/h
```

Press `q` inside the video window to stop the app.

If the popup does not appear, reinstall GUI OpenCV:

```bash
pip install -r requirements.txt
```

The repo uses `opencv-python`, not `opencv-python-headless`, because popup display requires GUI support.

## Event Schema

Each tracked object becomes one event:

```json
{
  "camera_id": "cam_01",
  "timestamp": "2026-04-28T16:22:12.123Z",
  "frame_id": 18422,
  "vehicle_id": "veh_203",
  "class": "car",
  "confidence": 0.93,
  "bbox": { "x": 412, "y": 178, "w": 82, "h": 46 },
  "centroid": { "x": 453, "y": 201 },
  "lane_id": "lane_1",
  "speed_estimate": 34.2
}
```

This event is sent to Kafka or stored in the offline buffer.

## Kafka Mode

For local demo without Kafka:

```env
KAFKA_ENABLED=false
```

For real Kafka publishing:

```env
KAFKA_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=traffic.events.raw
```

When Kafka is enabled and reachable, events are published to:

```text
traffic.events.raw
```

When Kafka is enabled but unreachable, events are automatically stored in SQLite.

## Offline Buffer

Offline events are stored in:

```text
data/offline_buffer.db
```

The buffer is persistent. If the count gets high during testing, clear it:

```powershell
Remove-Item data/offline_buffer.db
```

When Kafka reconnects, buffered events are flushed in chronological order.

## API And Metrics

The API server starts in the background.

Default:

```text
http://localhost:8001
```

If `8001` is busy, the app automatically uses the next free port, such as `8002`.

Endpoints:

```text
/health
/metrics
```

The Prometheus metric `detections_total` is incremented when detections occur.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the edge pipeline:

```bash
python -m src.main
```

Expected local-demo logs:

```text
YOLOv8 model loaded from yolov8n.pt
Kafka disabled; events will be written to the local offline buffer.
Processing started for camera: cam_01
Status: frames=67 total_detections=125 active_tracks=5 buffered_events=3423
```

## Test

Run all tests:

```bash
python -m pytest -q
```

Expected:

```text
4 passed
```

Run syntax/import check:

```bash
python -m compileall src tests scripts
```

## Demo Checklist

Before demo:

- Set `CAMERA_URL` to the correct video.
- Set `DISPLAY_VIDEO=true`.
- Set `KAFKA_ENABLED=false` if Kafka is not running.
- Set `FRAME_SKIP=0` for smoother visual boxes.
- Clear old buffer if you want a clean count.
- Run `python -m src.main`.
- Confirm the video window opens.
- Confirm green boxes show vehicle ID and speed.
- Press `q` to stop.

## Common Issues

`Kafka broker unavailable: NoBrokersAvailable`

Kafka is not running. Use `KAFKA_ENABLED=false` for local demo mode.

`API port 8001 is in use; using 8002 instead`

Another process is using port `8001`. This is fine; the app automatically chooses another port.

`lane=unknown`

The lane polygons do not match the video. Run `scripts/calibrate.py`.

No popup window

Make sure `DISPLAY_VIDEO=true` and `opencv-python` is installed.

Slow YOLO loading

The first model load can take time. The app logs progress before processing starts.

PyTorch `weights_only` warning

The repo includes a compatibility fallback for newer PyTorch versions loading older YOLO checkpoints. Use trusted local model files only.
