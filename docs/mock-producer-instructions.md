# Mock Kafka Producer — Implementation Instructions

**For:** B1 Developer  
**Purpose:** Continuously publish synthetic traffic events to Kafka so the B2 layer can be tested without real edge hardware running.  
**Your job:** Write and verify the script locally. DevOps handles all deployment.

---

## What you need to build

A single script: `scripts/mock_producer.py`

It must run continuously, generating fake but realistic traffic events and publishing them to the `traffic.events.raw` Kafka topic — the exact same topic the real edge pipeline writes to.

---

## Event schema

Every event you publish **must exactly match** this structure (same as what `build_event()` in `src/transport/kafka_producer.py` produces):

```json
{
  "camera_id": "cam_01",
  "timestamp": "2026-04-29T08:23:11.042Z",
  "vehicle_id": "veh_00042",
  "class": "car",
  "confidence": 0.91,
  "bbox": { "x": 412, "y": 178, "w": 82, "h": 46 },
  "centroid": { "x": 453, "y": 201 },
  "lane_id": 1,
  "speed_kmh": 34.2
}
```

**Rules:**
- `camera_id` — one of the configured cameras (e.g. `cam_01`, `cam_02`)
- `timestamp` — UTC ISO-8601 with milliseconds, format: `YYYY-MM-DDTHH:MM:SS.mmmZ`
- `vehicle_id` — string like `"veh_00042"`, incrementing per camera so IDs don't reset between events
- `class` — one of: `car`, `bus`, `truck`, `motorcycle`, `bicycle`, `pedestrian`
- `confidence` — float between 0.75 and 0.99
- `bbox` — dict with `x`, `y`, `w`, `h` as integers (pixels, within a 1920x1080 frame)
- `centroid` — dict with `x`, `y` as integers (`x + w//2`, `y + h//2` from bbox is fine)
- `lane_id` — integer, 1 or 2
- `speed_kmh` — float, realistic per class (see ranges below)

**Realistic speed ranges per class:**

| Class | Speed range (km/h) |
|---|---|
| car | 20 – 80 |
| bus | 15 – 55 |
| truck | 10 – 60 |
| motorcycle | 25 – 90 |
| bicycle | 5 – 25 |
| pedestrian | 2 – 8 |

**Vehicle class weights** (so output looks like real traffic):

| Class | Weight |
|---|---|
| car | 60% |
| motorcycle | 15% |
| truck | 10% |
| bus | 8% |
| bicycle | 5% |
| pedestrian | 2% |

---

## Environment variables

The script must read all config from env vars with these defaults:

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `KAFKA_TOPIC` | `traffic.events.raw` | Topic to publish to |
| `MOCK_CAMERAS` | `cam_01,cam_02` | Comma-separated list of camera IDs to simulate |
| `MOCK_EVENTS_PER_SEC` | `3` | Events per second **per camera** |

---

## Implementation requirements

1. **Use `kafka-python-ng` only** — it's already in `requirements.txt`. Do not add new dependencies. Use `KafkaProducer` directly (same as `TrafficKafkaProducer` in `src/transport/kafka_producer.py` — you can reference that for config).

2. **One loop per camera** — run each camera in its own thread so they publish independently.

3. **Vehicle ID continuity** — each camera keeps its own counter. IDs increment across events, never reset mid-run. Format: `"veh_{counter:05d}"` (e.g. `veh_00001`).

4. **Rate control** — sleep between events to match `MOCK_EVENTS_PER_SEC`. Use `time.sleep(1 / rate)`.

5. **Graceful shutdown** — handle `KeyboardInterrupt` (Ctrl+C) cleanly: stop threads, flush the producer, exit with code 0. No exception tracebacks on normal shutdown.

6. **Logging** — use Python's `logging` module (not `print`). Log at startup which cameras and rate are configured. Log a count of events sent every 30 seconds per camera (e.g. `cam_01: 90 events sent`). Log Kafka errors as warnings.

7. **Kafka connection failure on startup** — if Kafka is unreachable at startup, log a clear error and exit with code 1. Don't silently loop forever trying to reconnect.

---

## Script skeleton

```python
# scripts/mock_producer.py
import json, logging, os, random, threading, time
from kafka import KafkaProducer

# --- read env vars ---
# --- define vehicle classes + weights ---
# --- build_mock_event(camera_id, vehicle_counter) -> dict ---
# --- camera_loop(camera_id, producer, rate, stop_event) ---
#       loop: build event, producer.send(), sleep, log every 30s
# --- main() ---
#       create producer
#       start one thread per camera
#       block until KeyboardInterrupt
#       stop all threads, flush producer
```

---

## How to test locally

### 1. Start a local Kafka

From the project root (uses the existing `docker-compose.yml`):

```bash
docker compose up kafka zookeeper -d
```

Wait ~15 seconds for Kafka to be ready.

### 2. Run the script

```bash
# from project root
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
MOCK_CAMERAS=cam_01,cam_02 \
MOCK_EVENTS_PER_SEC=2 \
python scripts/mock_producer.py
```

You should see log output like:
```
INFO  Mock producer started: cameras=[cam_01, cam_02], rate=2 events/sec each
INFO  cam_01: 60 events sent
INFO  cam_02: 60 events sent
```

### 3. Verify events in Kafka

In a separate terminal, consume from the topic to confirm events are arriving and the schema is correct:

```bash
docker exec -it <kafka-container-name> \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic traffic.events.raw \
  --from-beginning
```

Check:
- [ ] Events are valid JSON
- [ ] All required fields are present with correct types
- [ ] `timestamp` is in `YYYY-MM-DDTHH:MM:SS.mmmZ` format
- [ ] Both `cam_01` and `cam_02` appear in the output
- [ ] `vehicle_id` values increment and don't repeat

### 4. Test graceful shutdown

Press `Ctrl+C` — the script must exit cleanly with no Python traceback.

---

## Definition of done

- [ ] `scripts/mock_producer.py` exists and runs without errors
- [ ] Events match the schema exactly (all fields, correct types)
- [ ] Both cameras publish independently at the configured rate
- [ ] Graceful Ctrl+C shutdown works
- [ ] Kafka connection failure at startup exits with code 1 and a clear error message
- [ ] Tested locally against the docker-compose Kafka and events confirmed via consumer

---

## What NOT to do

- Do not modify anything in `src/` — the mock producer is standalone
- Do not add new entries to `requirements.txt`
- Do not add a Dockerfile, Kubernetes manifest, or ArgoCD config — DevOps handles that
- Do not hardcode the Kafka address or topic — always read from env vars

---

## Hand-off

When done, commit `scripts/mock_producer.py` to the `main` branch with a commit message like:

```
Add continuous mock Kafka producer for B2 testing
```

Then let DevOps know — they will handle deploying it to the cluster.
