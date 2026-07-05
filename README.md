# Intelligent Traffic System (ITS) - Detection Edge

![Project Status](https://img.shields.io/badge/status-active-brightgreen.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)

The **ITS Detection Edge** is a specialized ML/AI microservice designed to operate directly at the edge layer of the Intelligent Traffic Ecosystem. This service is responsible for ingesting live video feeds, running lightweight object detection and tracking algorithms, and extracting highly valuable traffic metadata in real-time.

## 🚀 Edge Computing Strategy

Our core philosophy is to move the heavy processing to the edge, either on-camera or on low-resource edge computing devices. 

By utilizing highly efficient models like **YOLO** and **ByteTrack**, we perform intelligent vehicle detection, tracking, and metadata extraction (like speed estimation and lane identification) locally. **This drastically reduces the necessity of streaming raw, high-definition video over the network to the cloud, significantly preserving network bandwidth and lowering operational cloud ingestion costs.**

## ✨ Key Features

- **Real-Time Object Detection**: Uses **YOLO** to accurately detect vehicles (cars, trucks, buses, motorcycles) in varying traffic conditions.
- **Robust Object Tracking**: Integrates **ByteTrack** for consistent vehicle tracking across frames, enabling reliable speed and trajectory estimation.
- **Metadata Enrichment**: Enriches raw detections with advanced spatial metadata, including lane assignments and estimated vehicle speeds.
- **Resilient Event Publishing**: Publishes structured traffic events securely to **Apache Kafka** for downstream cloud aggregation and dashboarding.
- **Local Fallback Buffering**: Employs **SQLite** to buffer events locally during network outages or when the Kafka broker is unavailable, ensuring zero data loss.

## 🛠️ Architecture Overview

1. **Video Ingestion**: Connects to local video sources or IP cameras (RTSP/HTTP).
2. **ML Pipeline (YOLO + ByteTrack)**: Detects and tracks vehicles frame-by-frame.
3. **Analytics Engine**: Calculates speed and determines lane position using calibrated camera parameters.
4. **Data Dispatcher**: Formats the enriched data into standardized JSON payloads and dispatches them to Kafka (or SQLite).

## 💻 Installation & Quick Start

### Prerequisites
- Python 3.8+
- Requirements defined in `requirements.txt`

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Intelligent-Traffic-Ecosystem/its-detection-edge.git
   cd its-detection-edge
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Edge Service:**
   ```bash
   python -u -m src.main
   ```
   > **Note**: For local development and testing, the default video source is set to `tests/test.mp4`.

## 🧪 Testing & Calibration

Ensure you run tests locally before pushing changes.

**Run Unit Tests:**
```bash
python -m pytest -q
```

**Run Lane Calibration:**
If you need to define or recalibrate lanes based on a specific camera angle:
```bash
python scripts/calibrate.py --source tests/test.mp4 --output config/lanes.json
```

## 📖 Additional Documentation

For deeper technical details on the architecture, event schemas, and contribution guidelines, please refer to the [ML AI Engineer Guide](ML_AI_ENGINEER_GUIDE.md).
