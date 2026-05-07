# ITS Detection Edge

ML/AI edge service for the Intelligent Traffic System project. It reads a video feed, detects and tracks traffic objects with YOLO/ByteTrack, enriches events with lane and speed metadata, publishes to Kafka, and buffers events locally in SQLite when Kafka is unavailable.

## Quick Start

```bash
pip install -r requirements.txt
python -u -m src.main
```

For local testing, the default video source is `tests/test.mp4`.

## Useful Commands

```bash
python -m pytest -q
python scripts/calibrate.py --source tests/test.mp4 --output config/lanes.json
```

See `ML_AI_ENGINEER_GUIDE.md` for the detailed role guide and event schema.
