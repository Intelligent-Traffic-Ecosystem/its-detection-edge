import json
import os
import cv2

from src.ml.detector import VehicleDetector


def _load_ground_truth(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter_area / float(area_a + area_b - inter_area)


def test_accuracy():
    print("Running accuracy tests...")

    video_path = os.getenv("TEST_VIDEO_PATH")
    gt_path = os.getenv("GROUND_TRUTH_PATH")
    iou_threshold = float(os.getenv("IOU_THRESHOLD", 0.5))
    frame_skip = max(1, int(os.getenv("FRAME_SKIP", 3)))

    if not video_path or not gt_path:
        raise ValueError("TEST_VIDEO_PATH and GROUND_TRUTH_PATH must be set.")

    ground_truth = _load_ground_truth(gt_path)
    gt_by_frame = {item["frame_id"]: item.get("objects", []) for item in ground_truth}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ConnectionError("Failed to open test video.")

    detector = VehicleDetector()
    frame_id = 0
    total_matches = 0
    correct_class = 0

    while True:
        success, frame = cap.read()
        if not success:
            break
        frame_id += 1
        if frame_id % frame_skip != 0:
            continue

        detections = detector.detect_and_track(frame)
        gt_objects = gt_by_frame.get(frame_id, [])

        for gt in gt_objects:
            gt_box = gt["bbox"]
            best_iou = 0.0
            best_det = None
            for det in detections:
                x = det["bbox"]["x"]
                y = det["bbox"]["y"]
                w = det["bbox"]["w"]
                h = det["bbox"]["h"]
                det_box = [x, y, x + w, y + h]
                score = _iou(gt_box, det_box)
                if score > best_iou:
                    best_iou = score
                    best_det = det

            if best_det and best_iou >= iou_threshold:
                total_matches += 1
                if best_det["class"] == gt["class"]:
                    correct_class += 1

    cap.release()

    accuracy = (correct_class / total_matches) * 100 if total_matches else 0.0
    print(f"Matched detections: {total_matches}")
    print(f"Class accuracy: {accuracy:.2f}%")

    if accuracy < 85.0:
        raise AssertionError("Accuracy below 85%")

if __name__ == "__main__":
    test_accuracy()
