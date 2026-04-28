import os
from ultralytics import YOLO
import logging

# COCO class IDs for the 6 spec-required vehicle types
# car=2, bus=5, truck=7, motorcycle=3, bicycle=1, person=0
VEHICLE_CLASSES = {0: "pedestrian", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

class TrafficDetector:
    def __init__(self, model_path=None, confidence=None):
        model_path = model_path or os.getenv("MODEL_PATH", "yolov8n.pt")
        confidence = confidence or float(os.getenv("DETECTION_CONFIDENCE", "0.4"))
        self.model = YOLO(model_path)
        self.confidence = confidence
        logging.info(f"YOLOv8 model loaded from {model_path}")

    def detect_and_track(self, frame):
        """
        Runs detection and tracking on a single frame.
        Returns a list of tracked objects with metadata.
        """
        if frame is None:
            return []

        # Run tracking. persist=True maintains IDs across frames.
        # tracker="bytetrack.yaml" is the default for YOLOv8 but explicit is better.
        results = self.model.track(
            source=frame,
            conf=self.confidence,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False
        )

        tracked_objects = []
        
        # results[0] contains the results for the single frame input
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            clss = results[0].boxes.cls.cpu().numpy().astype(int)
            confs = results[0].boxes.conf.cpu().numpy()  # fixed: per-box confidence
            
            for box, track_id, cls, conf in zip(boxes, ids, clss, confs):
                # Filter to spec-required vehicle classes only
                if cls not in VEHICLE_CLASSES:
                    continue
                tracked_objects.append({
                    "id": int(track_id),
                    "bbox": box.tolist(),  # [x1, y1, x2, y2]
                    "class": VEHICLE_CLASSES[cls],
                    "confidence": float(conf)
                })

        return tracked_objects
