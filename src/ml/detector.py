from ultralytics import YOLO
import logging

class TrafficDetector:
    def __init__(self, model_path="yolov8n.pt", confidence=0.4):
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
            
            for box, track_id, cls in zip(boxes, ids, clss):
                tracked_objects.append({
                    "id": track_id,
                    "bbox": box.tolist(), # [x1, y1, x2, y2]
                    "class": self.model.names[cls],
                    "confidence": float(results[0].boxes.conf[0]) # Simplified for now
                })

        return tracked_objects
