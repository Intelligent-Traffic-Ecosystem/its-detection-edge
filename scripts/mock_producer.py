"""B1 mock producer — realistic traffic events for B2 dev/demo.

Each event matches B2's TrafficEventInput schema (camera_id, timestamp,
frame_id, vehicle_id, class, confidence, bbox, centroid, lane_id,
speed_estimate).

Previous version sent `speed_kmh`, which B2 silently dropped (pydantic
ignores unknown keys), forcing B2 to fall back to its pixel-displacement
SpeedTracker — and the placeholder pixel_to_meter constant produced 100–
400 km/h on the dashboard. This version emits `speed_estimate` so B2
uses the producer's speed directly.

Vehicles persist for multiple frames as they traverse the camera's field
of view; per-camera congestion drifts slowly, scaling both spawn rate
and observed speed. Coordinates assume B2's default pixel_to_meter
(0.05 m/px) so that even if `speed_estimate` is stripped downstream,
the SpeedTracker fallback would compute matching values.

Env vars:
  KAFKA_BOOTSTRAP_SERVERS  default localhost:9092
  KAFKA_TOPIC              default traffic.events.raw
  MOCK_CAMERAS             default "cam_01,cam_02"
  MOCK_EVENTS_PER_SEC      default 5  (per camera)
  MOCK_CAMERA_SPEEDS       default "cam_01:45,cam_02:35"
                           per-camera base speed in km/h
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
import time
from dataclasses import dataclass, field

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mock-producer")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "traffic.events.raw")
CAMERAS = [c.strip() for c in os.getenv("MOCK_CAMERAS", "cam_01,cam_02").split(",") if c.strip()]
EVENTS_PER_SEC = float(os.getenv("MOCK_EVENTS_PER_SEC", "5"))

# Per-camera base free-flow speed in km/h. Cameras not listed fall back to 40.
_DEFAULT_SPEEDS = "cam_01:45,cam_02:35"
CAMERA_BASES: dict[str, float] = {}
for entry in os.getenv("MOCK_CAMERA_SPEEDS", _DEFAULT_SPEEDS).split(","):
    if ":" in entry:
        k, v = entry.split(":", 1)
        try:
            CAMERA_BASES[k.strip()] = float(v)
        except ValueError:
            pass

VEHICLE_CLASSES = ["car", "motorcycle", "truck", "bus", "bicycle", "pedestrian"]
CLASS_WEIGHTS = [0.65, 0.18, 0.07, 0.04, 0.04, 0.02]
CLASS_BBOX = {
    "car": (90, 50),
    "motorcycle": (50, 35),
    "truck": (140, 70),
    "bus": (160, 80),
    "bicycle": (35, 30),
    "pedestrian": (25, 40),
}
# Relative to camera base speed.
CLASS_SPEED_FACTOR = {
    "car": 1.00,
    "motorcycle": 1.05,
    "truck": 0.85,
    "bus": 0.80,
    "bicycle": 0.30,
    "pedestrian": 0.10,
}

IMAGE_W, IMAGE_H = 1920, 1080
NUM_LANES = 2
# Matches B2's default speed_tracker_pixel_to_meter, so SpeedTracker fallback
# (if ever triggered) computes the same speed we set in speed_estimate.
PIXEL_TO_METER = 0.05


@dataclass
class Vehicle:
    vid: str
    cls: str
    lane: int
    speed_kmh: float
    cx: float
    cy: float
    vx: float
    vy: float
    bbox_w: int
    bbox_h: int


@dataclass
class Camera:
    cid: str
    base_speed_kmh: float
    congestion: float = 0.0
    last_tick: float = 0.0
    frame_counter: int = 0
    veh_counter: int = 0
    active: list[Vehicle] = field(default_factory=list)

    def _drift_congestion(self) -> None:
        # AR(1) toward a mild-traffic baseline (~0.35) with small noise.
        # Produces gentle peaks and troughs over tens of seconds.
        target = 0.35
        self.congestion = max(
            0.0,
            min(1.0, 0.97 * self.congestion + 0.03 * target + random.gauss(0, 0.04)),
        )

    def _spawn_rate(self) -> float:
        return 0.5 + 2.5 * self.congestion  # vehicles/sec

    def _speed_for(self, cls: str) -> float:
        base = self.base_speed_kmh * CLASS_SPEED_FACTOR[cls]
        s = base * (1 - 0.7 * self.congestion) + random.gauss(0, 2.5)
        return max(2.0, s)

    def _spawn(self) -> Vehicle:
        cls = random.choices(VEHICLE_CLASSES, weights=CLASS_WEIGHTS)[0]
        lane = random.randint(1, NUM_LANES)
        speed = self._speed_for(cls)
        direction = 1 if random.random() < 0.5 else -1
        cx = 0.0 if direction == 1 else float(IMAGE_W)
        cy = (lane - 0.5) * (IMAGE_H / NUM_LANES) + random.uniform(-50, 50)
        px_per_sec = (speed / 3.6) / PIXEL_TO_METER
        vx = direction * px_per_sec
        vy = random.gauss(0, 1.5)
        bw, bh = CLASS_BBOX[cls]
        bw = max(10, bw + random.randint(-10, 10))
        bh = max(10, bh + random.randint(-5, 5))
        self.veh_counter += 1
        vid = f"{self.cid}_v{self.veh_counter:06d}"
        return Vehicle(vid, cls, lane, speed, cx, cy, vx, vy, bw, bh)

    def tick(self, now: float) -> None:
        if self.last_tick == 0.0:
            self.last_tick = now
            return
        dt = now - self.last_tick
        self.last_tick = now
        self._drift_congestion()

        for v in self.active:
            v.cx += v.vx * dt
            v.cy += v.vy * dt
            # Smoothly nudge each vehicle's current speed toward target under
            # current congestion — simulates braking / acceleration with traffic.
            target = self._speed_for(v.cls)
            v.speed_kmh = 0.85 * v.speed_kmh + 0.15 * target
            v.vx = math.copysign((v.speed_kmh / 3.6) / PIXEL_TO_METER, v.vx)

        self.active = [v for v in self.active if -100 < v.cx < IMAGE_W + 100]

        expected = self._spawn_rate() * dt
        spawn_n = int(expected) + (1 if random.random() < expected - int(expected) else 0)
        for _ in range(spawn_n):
            self.active.append(self._spawn())

    def emit(self) -> dict:
        if not self.active:
            self.active.append(self._spawn())
        v = random.choice(self.active)
        self.frame_counter += 1
        return {
            "camera_id": self.cid,
            "timestamp": _timestamp(),
            "frame_id": self.frame_counter,
            "vehicle_id": v.vid,
            "class": v.cls,
            "confidence": round(random.uniform(0.75, 0.99), 3),
            "bbox": {
                "x": round(max(0.0, v.cx - v.bbox_w / 2), 1),
                "y": round(max(0.0, v.cy - v.bbox_h / 2), 1),
                "w": v.bbox_w,
                "h": v.bbox_h,
            },
            "centroid": {"x": round(v.cx, 1), "y": round(v.cy, 1)},
            "lane_id": v.lane,
            "speed_estimate": round(v.speed_kmh, 1),
        }


def _timestamp() -> str:
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(t)) + f"{int(t % 1 * 1000):03d}Z"


def camera_loop(cam: Camera, producer: KafkaProducer, rate: float, stop: threading.Event) -> None:
    interval = 1.0 / rate
    sent = 0
    last_log = time.time()
    while not stop.is_set():
        cam.tick(time.time())
        ev = cam.emit()
        try:
            producer.send(TOPIC, value=ev)
            sent += 1
        except Exception as e:
            log.warning("%s: send failed: %s", cam.cid, e)

        if time.time() - last_log >= 30:
            log.info(
                "%s: %d events sent  active=%d  congestion=%.2f",
                cam.cid, sent, len(cam.active), cam.congestion,
            )
            last_log = time.time()
        stop.wait(interval)


def main() -> None:
    log.info("Connecting to Kafka at %s ...", BOOTSTRAP_SERVERS)
    try:
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
            linger_ms=50,
            request_timeout_ms=5000,
        )
    except NoBrokersAvailable:
        log.error("No Kafka brokers available at %s — exiting.", BOOTSTRAP_SERVERS)
        raise SystemExit(1)

    cams = [Camera(cid, CAMERA_BASES.get(cid, 40.0)) for cid in CAMERAS]
    log.info(
        "Mock producer started: cameras=%s rate=%.1f events/sec each",
        [(c.cid, c.base_speed_kmh) for c in cams], EVENTS_PER_SEC,
    )

    stop = threading.Event()
    threads = [
        threading.Thread(target=camera_loop, args=(c, producer, EVENTS_PER_SEC, stop), daemon=True)
        for c in cams
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        stop.set()
        for t in threads:
            t.join(timeout=3)
        producer.flush(timeout=5)
        producer.close()
        log.info("Stopped.")


if __name__ == "__main__":
    main()
