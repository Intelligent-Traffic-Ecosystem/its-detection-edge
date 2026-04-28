"""
Accuracy test — AC-01, AC-02, AC-03 from B1 spec.
  - AC-01: events reach Kafka within 500ms (measured as detection latency)
  - AC-02: same vehicle keeps same ID for ≥10 frames
  - AC-03: vehicle class confidence ≥85% average on test video

Usage:
    python tests/accuracy_test.py
"""
import sys
import os
import time
import collections

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml.detector import TrafficDetector, VEHICLE_CLASSES
import cv2

TEST_VIDEO = os.path.join(os.path.dirname(__file__), "test_video.mp4")
MIN_CONFIDENCE = 0.85
MIN_TRACKING_FRAMES = 10


def test_accuracy():
    print("=" * 60)
    print("B1 Accuracy Test — Detection, Tracking & Confidence")
    print("=" * 60)

    if not os.path.exists(TEST_VIDEO):
        print(f"[SKIP] Test video not found: {TEST_VIDEO}")
        print("       Place a test video at tests/test_video.mp4 to run.")
        return

    detector = TrafficDetector()
    cap = cv2.VideoCapture(TEST_VIDEO)

    if not cap.isOpened():
        print("[FAIL] Cannot open test video.")
        sys.exit(1)

    total_detections = 0
    high_conf_detections = 0
    class_counts = collections.Counter()
    # track_id -> list of frame indices where it appeared
    track_frames = collections.defaultdict(list)
    latencies = []
    frame_idx = 0

    print(f"\nRunning detection on: {TEST_VIDEO}")
    print("Processing frames...\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        t_start = time.time()
        results = detector.detect_and_track(frame)
        latency_ms = (time.time() - t_start) * 1000
        latencies.append(latency_ms)

        for obj in results:
            total_detections += 1
            class_counts[obj["class"]] += 1
            track_frames[obj["id"]].append(frame_idx)
            if obj["confidence"] >= MIN_CONFIDENCE:
                high_conf_detections += 1

        frame_idx += 1

    cap.release()

    # --- Report ---
    print(f"Frames processed  : {frame_idx}")
    print(f"Total detections  : {total_detections}")
    print(f"\nClass distribution:")
    for cls, count in sorted(class_counts.items()):
        print(f"  {cls:<15}: {count}")

    # AC-03: confidence
    conf_rate = (high_conf_detections / total_detections * 100) if total_detections > 0 else 0
    print(f"\nAC-03 Confidence ≥{MIN_CONFIDENCE*100:.0f}%: {conf_rate:.1f}%  ", end="")
    ac03_pass = conf_rate >= (MIN_CONFIDENCE * 100)
    print("PASS ✓" if ac03_pass else "FAIL ✗")

    # AC-02: tracking stability
    stable_tracks = [tid for tid, frames in track_frames.items() if len(frames) >= MIN_TRACKING_FRAMES]
    print(f"\nAC-02 Stable tracks (≥{MIN_TRACKING_FRAMES} frames): {len(stable_tracks)}", end="  ")
    ac02_pass = len(stable_tracks) > 0
    print("PASS ✓" if ac02_pass else "FAIL ✗ (no vehicle tracked across ≥10 frames)")

    # AC-01: detection latency proxy (should be < 500ms per frame)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    print(f"\nAC-01 Avg detection latency: {avg_latency:.1f}ms  ", end="")
    ac01_pass = avg_latency < 500
    print("PASS ✓" if ac01_pass else "FAIL ✗")

    print("\n" + "=" * 60)
    overall = ac01_pass and ac02_pass and ac03_pass
    print("RESULT:", "ALL PASS ✓" if overall else "SOME CHECKS FAILED ✗")
    print("=" * 60)

    if not overall:
        sys.exit(1)


if __name__ == "__main__":
    test_accuracy()
