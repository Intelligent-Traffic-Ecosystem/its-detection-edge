import json
import logging
import os
import random
import threading
import time

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC             = os.getenv("KAFKA_TOPIC", "traffic.events.raw")
CAMERAS           = os.getenv("MOCK_CAMERAS", "cam_01,cam_02").split(",")
EVENTS_PER_SEC    = float(os.getenv("MOCK_EVENTS_PER_SEC", "3"))

VEHICLE_CLASSES = ["car", "motorcycle", "truck", "bus", "bicycle", "pedestrian"]
WEIGHTS         = [0.60,  0.15,         0.10,   0.08,  0.05,      0.02]

SPEED_RANGES = {
    "car":         (20, 80),
    "motorcycle":  (25, 90),
    "truck":       (10, 60),
    "bus":         (15, 55),
    "bicycle":     (5,  25),
    "pedestrian":  (2,   8),
}


def _timestamp():
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(t)) + f"{int(t % 1 * 1000):03d}Z"


def build_event(camera_id, counter):
    cls        = random.choices(VEHICLE_CLASSES, weights=WEIGHTS)[0]
    lo, hi     = SPEED_RANGES[cls]
    speed      = round(random.uniform(lo, hi), 1)
    confidence = round(random.uniform(0.75, 0.99), 3)
    x          = random.randint(0, 1800)
    y          = random.randint(0, 1000)
    w          = random.randint(40, 160)
    h          = random.randint(25, 90)
    return {
        "camera_id":  camera_id,
        "timestamp":  _timestamp(),
        "vehicle_id": f"veh_{counter:05d}",
        "class":      cls,
        "confidence": confidence,
        "bbox":       {"x": x, "y": y, "w": w, "h": h},
        "centroid":   {"x": x + w // 2, "y": y + h // 2},
        "lane_id":    random.randint(1, 2),
        "speed_kmh":  speed,
    }


def camera_loop(camera_id, producer, rate, stop_event):
    interval = 1.0 / rate
    counter  = 1
    sent     = 0
    last_log = time.time()

    while not stop_event.is_set():
        event = build_event(camera_id, counter)
        try:
            producer.send(TOPIC, value=event)
            counter += 1
            sent    += 1
        except Exception as e:
            logging.warning("%s: send failed: %s", camera_id, e)

        if time.time() - last_log >= 30:
            logging.info("%s: %d events sent", camera_id, sent)
            last_log = time.time()

        stop_event.wait(interval)


def main():
    logging.info("Connecting to Kafka at %s ...", BOOTSTRAP_SERVERS)
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
        logging.error("No Kafka brokers available at %s — exiting.", BOOTSTRAP_SERVERS)
        raise SystemExit(1)

    logging.info("Mock producer started: cameras=%s, rate=%.1f events/sec each", CAMERAS, EVENTS_PER_SEC)

    stop_event = threading.Event()
    threads = [
        threading.Thread(target=camera_loop, args=(cam, producer, EVENTS_PER_SEC, stop_event), daemon=True)
        for cam in CAMERAS
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        stop_event.set()
        for t in threads:
            t.join(timeout=3)
        producer.flush(timeout=5)
        producer.close()
        logging.info("Stopped.")


if __name__ == "__main__":
    main()
