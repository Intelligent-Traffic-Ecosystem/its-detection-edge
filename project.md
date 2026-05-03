
---

# GROUP B — B1 EDGE LAYER
**Intelligent Traffic System | 4 Members | 2-Week Sprint**

---

## What Each Person Builds

### 1. HARDWARE ENGINEER — Cameras, Pi 5 & Physical Setup
Responsible for the physical layer. Everything else depends on this role.

**Tasks:**
- Set up Raspberry Pi 5 — install Balena OS, register it in BalenaCloud
- Connect and verify all cameras — USB cameras via /dev/videoN, IP cameras via RTSP URL
- Create lanes.json for each camera — draw lane polygons using calibrate.py, measure pixel-to-metre ratio
- Test camera disconnects — unplug each camera, confirm the container retries every 5s and others keep running
- Run the junction for 10 minutes — all cameras live simultaneously, no crashes

**Output:** Pi 5 online in Balena, all cameras streaming, one lanes.json per camera, test evidence.

---

### 2. ML / AI ENGINEER — Detection, Tracking, Kafka & Buffer
Builds the brain of B1. Raw frames come in, structured vehicle events go out. Also owns the Kafka producer and offline buffer.

**Tasks:**
- Frame capture — read from USB or IP camera using OpenCV, apply FRAME_SKIP
- YOLOv8n detection — output bbox, centroid, class (car/bus/truck/motorcycle/bicycle/pedestrian), confidence
- ByteTrack tracking — assign stable vehicle_id across frames
- Speed estimator — calculate km/h from centroid movement between frames
- Kafka producer — publish JSON events to traffic.events.raw, acks=all
- SQLite offline buffer — save events to disk when Kafka is down, replay when it comes back
- Accuracy test — run on test video, confirm class labels are correct ≥85% of the time
- Sample .jsonl file — 5 minutes of real detection events, send to L2 team by Day 7

**Output:** Working detection pipeline, events flowing into Kafka, buffer tested, .jsonl file delivered to L2.

---

### 3. SOFTWARE ENGINEER — Enrichment, APIs & Integration
Connects everything together and makes B1 observable.

**Tasks:**
- Lane ROI enricher — read lanes.json, map each detection centroid to a lane, attach lane_id
- RTSP fallback server — expose raw video via GStreamer so L2 can run its own detection if needed
- Multi-camera isolation — one container per camera — a crash in one does not stop the others
- /health endpoint — return HTTP 200 only when camera is live AND Kafka producer is connected
- Prometheus /metrics endpoint — expose frame rate, detections per second, Kafka publish rate, buffer depth
- docker-compose.yml — local 2-camera test setup for the team to run offline
- Integration tests — verify AC-01 (latency), AC-04 (Kafka outage), AC-05 (disconnect), AC-08 (L2 confirm)

**Output:** Lane enricher, /health, /metrics, RTSP fallback, docker-compose.yml, and passing integration tests.

---

### 4. DEVOPS ENGINEER — Docker, Balena, CI/CD & Platform
Makes sure everything runs in production and that L4 can see and manage it.

**Tasks:**
- Dockerfile — package the full Python pipeline — YOLOv8n, OpenCV, Kafka, GStreamer
- Balena fleet config — set all env vars, store camera and Kafka credentials as Balena Secrets
- OTA update tested — push a change via BalenaCloud, confirm Pi 5 updates without SSH
- Kafka broker confirmed — get host:port from L4, set KAFKA_BROKERS in fleet variables
- CI/CD pipeline — GitHub Actions — test → build → push image → Balena deploy on every merge to main
- L4 sign-off — written confirmation from L4 that /health, /metrics, Kafka, and containers are all accepted

**Output:** Dockerfile, Balena fleet running OTA, CI/CD pipeline live, and L4 written sign-off.

---

## What B1 Looks Like When Fully Done

The full flow from power-on to data reaching L2:

1. **Pi 5 boots** — Balena OS starts, supervisor pulls the latest Docker image, launches one container per camera automatically. No manual setup needed.
2. **Cameras come online** — Each container opens its assigned camera (USB or IP). Failed cameras retry every 5 seconds; others keep running unaffected.
3. **Frames are captured and processed** — OpenCV samples frames. YOLOv8n detects and labels every vehicle. ByteTrack assigns stable IDs across frames.
4. **Each detection is enriched** — Lane enricher maps vehicle lane position. Speed estimator calculates velocity. Both values are added to the event.
5. **Events are published to Kafka** — A complete JSON event (camera ID, timestamp, vehicle ID, class, speed, lane) is sent to traffic.events.raw within 500ms of vehicle appearance.
6. **Outages are handled automatically** — If Kafka goes down, events are saved locally in SQLite and replayed in order when Kafka returns. No data lost, no manual intervention needed.
7. **L2 receives the data** — L2 AI layer consumes events from Kafka, runs congestion analysis, and serves results to the dashboard. B1's job ends once the event lands in Kafka.
8. **L4 monitors everything** — L4 scrapes /metrics every 15 seconds. /health tells L4 whether each camera and Kafka connection is alive. Alerts fire if anything drops.
9. **Updates deploy with no SSH** — On every merge to main, GitHub Actions builds a new image and Balena delivers it to the Pi 5 over the air.

---

## Completion Checklist

| # | What We Check | Owner |
|---|---|---|
| 1 | Events reach Kafka within 500ms of a vehicle appearing on camera | ML/AI |
| 2 | The same vehicle keeps the same ID for at least 10 frames | ML/AI |
| 3 | Vehicle class is correct 85% of the time on the test video | ML/AI |
| 4 | Events are saved and replayed correctly after a 60-second Kafka outage | ML/AI |
| 5 | Unplugging a camera does not crash the other containers | Hardware |
| 6 | A Balena OTA update reaches the Pi without any SSH access | DevOps |
| 7 | L4 Prometheus can scrape the /metrics endpoint | DevOps |
| 8 | L2 confirms they can consume events and see congestion data | Software |
| 9 | Sample .jsonl file delivered to L2 by Day 7 | Software |

**B1 is complete when:** The Pi 5 is running at the junction, detecting every vehicle, publishing events to Kafka, surviving failures on its own, and giving L4 full visibility — with L2 able to build everything it needs on top of what B1 produces.