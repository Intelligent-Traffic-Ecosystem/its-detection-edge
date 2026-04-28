"""
Generate a sample .jsonl file from the test video.
This produces the Day-7 deliverable for the L2 team.

Output: output/sample_events.jsonl
Usage : python scripts/generate_sample_jsonl.py

Each line is one JSON event matching the Kafka event schema:
{
  "camera_id": "cam_01",
  "timestamp": 1714235000.123,
  "vehicle": {
    "id": 5,
    "type": "car",
    "speed": 32.4,
    "lane": "lane_1",
    "bbox": [x1, y1, x2, y2]
  }
}
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml.detector import TrafficDetector
from src.analytics.enricher import LaneEnricher
from src.analytics.speed import SpeedCalculator
import cv2

# --- Config ---
VIDEO_PATH   = os.path.join("tests", "test_video.mp4")
LANES_CONFIG = os.path.join("config", "lanes.json")
OUTPUT_DIR   = "output"
OUTPUT_FILE  = os.path.join(OUTPUT_DIR, "sample_events.jsonl")
CAMERA_ID    = os.getenv("CAMERA_ID", "cam_01")
FRAME_SKIP   = int(os.getenv("FRAME_SKIP", "2"))


def main():
    if not os.path.exists(VIDEO_PATH):
        print(f"[ERROR] Video not found: {VIDEO_PATH}")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(LANES_CONFIG) as f:
        lanes_cfg = json.load(f)

    detector   = TrafficDetector()
    enricher   = LaneEnricher(lanes_cfg)
    speed_calc = SpeedCalculator()
    cap        = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {VIDEO_PATH}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    event_count = 0
    frame_idx   = 0

    print(f"Generating sample events from: {VIDEO_PATH}")
    print(f"Output -> {OUTPUT_FILE}\n")

    with open(OUTPUT_FILE, "w") as out:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            # Apply FRAME_SKIP
            if frame_idx % (FRAME_SKIP + 1) != 0:
                continue

            timestamp = time.time()
            tracked   = detector.detect_and_track(frame)
            current_ids = []

            for obj in tracked:
                current_ids.append(obj["id"])
                obj["lane_id"]   = enricher.map_to_lane(obj["bbox"])
                obj["speed_kmh"] = speed_calc.calculate_speed(obj["id"], obj["bbox"], timestamp)

                event = {
                    "camera_id": CAMERA_ID,
                    "timestamp": timestamp,
                    "vehicle": {
                        "id":    obj["id"],
                        "type":  obj["class"],
                        "speed": obj["speed_kmh"],
                        "lane":  obj["lane_id"],
                        "bbox":  obj["bbox"]
                    }
                }
                out.write(json.dumps(event) + "\n")
                event_count += 1

            speed_calc.clear_old_tracks(current_ids)

    cap.release()
    print(f"Done. {event_count} events written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
