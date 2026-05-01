import cv2
import numpy as np
import time
from ultralytics import YOLO

# --- Configuration ---
VIDEO_PATH = "tests/test2.mp4"
MODEL_PATH = "yolov8n.pt"
FRAME_SKIP = 3
CONFIDENCE_THRESHOLD = 0.45
PIXEL_TO_METRE = 0.045 # Mock ratio: 1 pixel = 0.045 metres

# COCO class mapping for YOLOv8
# 0: person (pedestrian), 1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck
ALLOWED_CLASSES = [0, 1, 2, 3, 5, 7]

# --- Mock Lane Configuration ---
# Defining two simple polygonal zones representing lanes in a 640x480 frame
MOCK_LANES = {
    "lane_1": np.array([[100, 480], [300, 480], [300, 200], [100, 200]], np.int32),
    "lane_2": np.array([[320, 480], [520, 480], [520, 200], [320, 200]], np.int32)
}

def get_lane_id(centroid):
    """
    Checks if a centroid falls within any of the defined mock lanes.
    """
    for lane_id, polygon in MOCK_LANES.items():
        # pointPolygonTest returns >= 0 if the point is inside or on the edge of the polygon
        if cv2.pointPolygonTest(polygon, centroid, False) >= 0:
            return lane_id
    return "unknown"

def main():
    print(f"Loading YOLO model from {MODEL_PATH}...")
    try:
        model = YOLO(MODEL_PATH)
    except Exception as e:
        print(f"Failed to load model: {e}")
        return
    
    print(f"Opening video {VIDEO_PATH}...")
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"Error: Could not open video stream from {VIDEO_PATH}")
        return

    # Dictionary to store previous track states for speed estimation
    # Format: { vehicle_id: (centroid_tuple, timestamp_float) }
    track_history = {}
    
    frame_count = 0
    
    print("Starting B1 Edge Layer pipeline processing. Press 'q' to stop.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("End of video stream reached.")
            break
            
        frame_count += 1
        
        # 1. Video Ingestion: Frame skipping logic
        if frame_count % FRAME_SKIP != 0:
            continue
            
        # 1. Video Ingestion: Resize frame to 640x480
        frame = cv2.resize(frame, (640, 480))
        current_time = time.time()
        
        # 2. Detection & Tracking: Ultralytics YOLOv8 & ByteTrack
        # Using persist=True allows the tracker to maintain IDs across frames
        results = model.track(
            frame, 
            persist=True, 
            tracker="bytetrack.yaml", 
            classes=ALLOWED_CLASSES, 
            conf=CONFIDENCE_THRESHOLD, 
            verbose=False
        )
        
        # Process detection results
        if results and results[0].boxes and results[0].boxes.id is not None:
            # Extract tracking info from the GPU to CPU/NumPy
            boxes = results[0].boxes.xywh.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy()
            classes = results[0].boxes.cls.int().cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            
            for box, track_id, cls_id, conf in zip(boxes, track_ids, classes, confs):
                # box is [x_center, y_center, width, height]
                x_center, y_center, w, h = box
                centroid = (float(x_center), float(y_center))
                
                # --- 3. Enrichment: Lane ---
                lane_id = get_lane_id(centroid)
                
                # --- 3. Enrichment: Speed Estimation ---
                speed_kmh = 0.0
                if track_id in track_history:
                    prev_centroid, prev_time = track_history[track_id]
                    dt = current_time - prev_time
                    
                    if dt > 0:
                        # Calculate pixel displacement using Euclidean distance
                        dx = centroid[0] - prev_centroid[0]
                        dy = centroid[1] - prev_centroid[1]
                        dist_pixels = np.sqrt(dx**2 + dy**2)
                        
                        # Convert pixel displacement to metres
                        dist_metres = dist_pixels * PIXEL_TO_METRE
                        
                        # Calculate speed (m/s) and convert to km/h
                        speed_mps = dist_metres / dt
                        speed_kmh = speed_mps * 3.6
                
                # Update history for this vehicle's next frame
                track_history[track_id] = (centroid, current_time)
                
                # --- Visualization / Output ---
                # Calculate top-left and bottom-right coords for bounding box
                x1, y1 = int(x_center - w / 2), int(y_center - h / 2)
                x2, y2 = int(x_center + w / 2), int(y_center + h / 2)
                
                class_name = model.names[cls_id]
                label = f"ID:{track_id} {class_name} {conf:.2f} | {lane_id} | {speed_kmh:.1f}km/h"
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 2)
        
        # Draw the mock lanes for visual reference
        for lane_id, polygon in MOCK_LANES.items():
            cv2.polylines(frame, [polygon], isClosed=True, color=(255, 0, 0), thickness=2)
            cv2.putText(frame, lane_id, tuple(polygon[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
        # Display the processed frame
        cv2.imshow("B1 Edge Layer Test", frame)
        
        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("User interrupted processing.")
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    print("Pipeline execution completed.")

if __name__ == "__main__":
    main()
