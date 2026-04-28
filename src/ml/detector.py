import logging
import pickle

class TrafficDetector:
    DEFAULT_CLASSES = {"car", "motorcycle", "bus", "truck", "person", "bicycle"}

    def __init__(
        self,
        model_path="yolov8n.pt",
        confidence=0.4,
        tracker_config="bytetrack.yaml",
        frame_skip=0,
        allowed_classes=None,
        model=None,
    ):
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
