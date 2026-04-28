import os
import logging
import pickle

# COCO class IDs for the 6 spec-required vehicle types
# car=2, bus=5, truck=7, motorcycle=3, bicycle=1, person=0
VEHICLE_CLASSES = {0: "pedestrian", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class TrafficDetector:
    DEFAULT_CLASSES = {"car", "motorcycle", "bus", "truck", "person", "bicycle"}

    def __init__(
        self,
        model_path=None,
        confidence=None,
        tracker_config="bytetrack.yaml",
        frame_skip=0,
        allowed_classes=None,
        model=None,
    ):
        model_path = model_path or os.getenv("MODEL_PATH", "yolov8n.pt")
        confidence = confidence if confidence is not None else float(os.getenv("DETECTION_CONFIDENCE", "0.4"))

        if model is None:
            model = self._load_yolo_model(model_path)

        self.model = model
        self.confidence = float(confidence)
        self.tracker_config = tracker_config
        self.frame_skip = max(0, int(frame_skip))
        self.allowed_classes = set(allowed_classes or self.DEFAULT_CLASSES)
        self.frame_index = 0
        logging.info("YOLOv8 model loaded from %s", model_path)

    def _load_yolo_model(self, model_path):
        from ultralytics import YOLO

        try:
            return YOLO(model_path)
        except pickle.UnpicklingError as exc:
            if "Weights only load failed" not in str(exc):
                raise

            logging.warning(
                "Retrying YOLO model load with torch weights_only=False for PyTorch 2.6+ compatibility. "
                "Use only trusted local model files."
            )
            import torch

            original_load = torch.load

            def torch_load_compat(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return original_load(*args, **kwargs)

            torch.load = torch_load_compat
            try:
                return YOLO(model_path)
            finally:
                torch.load = original_load

    def detect_and_track(self, frame):
        """
        Runs detection and tracking on a single frame.
        Returns a list of tracked objects with metadata.
        """
        if frame is None:
            return []

        self.frame_index += 1
        if self.frame_skip and (self.frame_index - 1) % (self.frame_skip + 1) != 0:
            return []

        # Run tracking. persist=True maintains IDs across frames.
        # tracker="bytetrack.yaml" is the default for YOLOv8 but explicit is better.
        results = self.model.track(
            source=frame,
            conf=self.confidence,
            persist=True,
            tracker=self.tracker_config,
            verbose=False
        )

        tracked_objects = []

        if not results:
            return tracked_objects

        # results[0] contains the results for the single frame input
        result = results[0]
        if result.boxes is not None and result.boxes.id is not None:
            boxes = result.boxes.xyxy.cpu().numpy()
            ids = result.boxes.id.cpu().numpy().astype(int)
            clss = result.boxes.cls.cpu().numpy().astype(int)
            confidences = result.boxes.conf.cpu().numpy()

            for box, track_id, cls, confidence in zip(boxes, ids, clss, confidences):
                label = self.model.names[int(cls)]
                if label not in self.allowed_classes:
                    continue

                x1, y1, x2, y2 = [float(v) for v in box]
                tracked_objects.append({
                    "id": track_id,
                    "vehicle_id": f"veh_{track_id}",
                    "bbox": [x1, y1, x2, y2],
                    "bbox_xywh": {
                        "x": round(x1, 2),
                        "y": round(y1, 2),
                        "w": round(x2 - x1, 2),
                        "h": round(y2 - y1, 2),
                    },
                    "centroid": {
                        "x": round((x1 + x2) / 2, 2),
                        "y": round((y1 + y2) / 2, 2),
                    },
                    "class": label,
                    "confidence": round(float(confidence), 4),
                    "frame_id": self.frame_index,
                })

        return tracked_objects


class VehicleDetector:
    """Simplified detector interface compatible with the kisaja branch implementation."""

    def __init__(self, confidence_threshold=0.45):
        from ultralytics import YOLO

        model_path = os.getenv("MODEL_PATH", "yolov8n.pt")
        self.model = YOLO(model_path)
        self.conf_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", confidence_threshold))
        self.tracker_config = os.getenv("TRACKER_CONFIG", "bytetrack.yaml")
        self.target_classes = list(VEHICLE_CLASSES.keys())
        self.class_names = VEHICLE_CLASSES

    def detect_and_track(self, frame):
        """Returns a list of vehicle dicts with vehicle_id, class, confidence, bbox, centroid."""
        results = self.model.track(
            frame,
            persist=True,
            tracker=self.tracker_config,
            conf=self.conf_threshold,
            classes=self.target_classes,
            verbose=False,
        )

        detected_vehicles = []

        if results[0].boxes.id is None:
            return detected_vehicles

        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.int().cpu().tolist()
        classes = results[0].boxes.cls.int().cpu().tolist()
        confidences = results[0].boxes.conf.cpu().tolist()

        for box, track_id, cls_id, conf in zip(boxes, track_ids, classes, confidences):
            x1, y1, x2, y2 = map(int, box)
            w = x2 - x1
            h = y2 - y1
            centroid_x = int(x1 + w / 2)
            centroid_y = int(y1 + h / 2)

            detected_vehicles.append({
                "vehicle_id": f"veh_{track_id}",
                "class": self.class_names[cls_id],
                "confidence": round(conf, 2),
                "bbox": {"x": x1, "y": y1, "w": w, "h": h},
                "centroid": {"x": centroid_x, "y": centroid_y},
            })

        return detected_vehicles
