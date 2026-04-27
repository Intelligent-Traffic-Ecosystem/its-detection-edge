import cv2
from ultralytics import YOLO

class VehicleDetector:
    def __init__(self, confidence_threshold=0.45):
        """
        Initializes the YOLOv8 nano model.
        It will automatically download the 'yolov8n.pt' weights the first time it runs.
        """
        # YOLOv8n is chosen because it runs fast on a Raspberry Pi 5 CPU
        self.model = YOLO('yolov8s.pt') 
        self.conf_threshold = confidence_threshold
        
        # In the COCO dataset (which YOLOv8 is trained on), the IDs for vehicles are:
        # 0: pedestrian, 1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck
        self.target_classes = [0, 1, 2, 3, 5, 7]
        
        # Map the numeric IDs back to the string names required by the L2 layer
        self.class_names = {
            0: "pedestrian",
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck"
        }

    def detect_and_track(self, frame):
        """
        Takes an OpenCV video frame, runs detection, and assigns stable IDs.
        Returns a list of dictionaries containing the extracted vehicle data.
        """
        # Run YOLO inference with built-in ByteTrack tracking
        results = self.model.track(
            frame, 
            persist=True,               # Keep IDs stable across frames
            tracker="bytetrack.yaml",   # Use ByteTrack algorithm
            conf=self.conf_threshold,   # Filter out low-confidence guesses
            classes=self.target_classes,# Only look for our specific vehicle types
            verbose=False               # Keep the terminal clean
        )

        detected_vehicles = []

        # If the model didn't find anything, return an empty list early
        if results[0].boxes.id is None:
            return detected_vehicles

        # Extract the data from the Ultralytics results object
        boxes = results[0].boxes.xyxy.cpu().numpy()     # Bounding box coordinates
        track_ids = results[0].boxes.id.int().cpu().tolist() # ByteTrack IDs
        classes = results[0].boxes.cls.int().cpu().tolist()  # Vehicle class IDs
        confidences = results[0].boxes.conf.cpu().tolist()   # Confidence scores

        # Loop through every vehicle found in this specific frame
        for box, track_id, cls_id, conf in zip(boxes, track_ids, classes, confidences):
            x1, y1, x2, y2 = map(int, box)
            
            # Calculate width and height
            w = x2 - x1
            h = y2 - y1
            
            # Calculate the center point (centroid)
            centroid_x = int(x1 + (w / 2))
            centroid_y = int(y1 + (h / 2))

            # Package the data exactly how the L2 team expects it
            vehicle_data = {
                "vehicle_id": f"veh_{track_id}",
                "class": self.class_names[cls_id],
                "confidence": round(conf, 2),
                "bbox": {"x": x1, "y": y1, "w": w, "h": h},
                "centroid": {"x": centroid_x, "y": centroid_y}
            }
            
            detected_vehicles.append(vehicle_data)

        return detected_vehicles