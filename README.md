# ITS Detection Edge

ML/AI edge service for the Intelligent Traffic System project. It reads a video feed, detects and tracks traffic objects with YOLO/ByteTrack, enriches events with lane and speed metadata, publishes to Kafka, and buffers events locally in SQLite when Kafka is unavailable.

## Quick Start

```bash
pip install -r requirements.txt
python -u -m src.main
```

For local testing, the default video source is `tests/test.mp4`.

## Kafka

Start Kafka:

```bash
docker compose up -d kafka
```

Enable Kafka in `.env`:

```env
KAFKA_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=traffic.events.raw
```

Check the topic:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

## Useful Commands

```bash
python -m pytest -q
python scripts/calibrate.py --source tests/test.mp4 --output config/lanes.json
```

See `ML_AI_ENGINEER_GUIDE.md` for the detailed role guide and event schema.
