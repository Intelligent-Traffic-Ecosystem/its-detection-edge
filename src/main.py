import os
import time
import json
from datetime import datetime, timezone
import cv2
from dotenv import load_dotenv
load_dotenv()

# Import the classes we just built
from capture.camera import VideoCaptureManager
from ml.detector import VehicleDetector
from analytics.speed import SpeedEstimator

def main():
    # 1. Setup Cvvonfiguration
    camera_id = os.getenv("CAMERA_ID", "cam_test_01")
    frame_skip = int(os.getenv("FRAME_SKIP", 3))
    
    print(f"Starting B1 Edge Node for camera: {camera_id}")
    
    # 2. Initialize our modules
    try:
        camera = VideoCaptureManager()
        detector = VehicleDetector(confidence_threshold=0.45)
        speed_estimator = SpeedEstimator(pixel_to_metre=0.045, video_fps=25, frame_skip=3)
    except Exception as e:
        # The L4 DevOps team requires errors to be structured JSON
        print(json.dumps({"level": "error", "message": str(e)}))
        return

    frame_id = 0

    # 3. The Main Processing Loop
    try:
        while True:
            # Grab a frame (this automatically handles the FRAME_SKIP logic!)
            frame = camera.get_processed_frame()
            
            if frame is None:
                # If the camera drops, the SRS says to retry every 5 seconds
                print(json.dumps({"level": "warning", "message": "Camera dropped. Retrying in 5s..."}))
                time.sleep(5)
                # In a production environment, you might try to re-initialize the camera here
                continue

            frame_id += 1
            
            # Run the YOLO + ByteTrack inference
            detected_vehicles = detector.detect_and_track(frame)
            
            # Generate the current UTC timestamp (required by L2)
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            # 4. Format and Output the Data
            for vehicle in detected_vehicles:
                # Build the exact JSON schema requested by the L2 team
                calculated_speed = speed_estimator.estimate_speed(vehicle["vehicle_id"], vehicle["centroid"])
                event_payload = {
                    "camera_id": camera_id,
                    "timestamp": current_time,
                    "frame_id": frame_id,
                    "vehicle_id": vehicle["vehicle_id"],
                    "class": vehicle["class"],
                    "confidence": vehicle["confidence"],
                    "bbox": vehicle["bbox"],
                    "centroid": vehicle["centroid"],
                    "speed_estimate_kmh": calculated_speed
                    # Note: lane_id and speed_estimate will be added in Week 2
                }
                
                # Print the JSON string to the terminal so L4 can ingest it via ELK stack
                print(json.dumps(event_payload))

            # --- VISUAL DEBUGGING (Optional: Remove before giving to DevOps) ---
            # Draw the bounding boxes on the frame so you can see it working
            for v in detected_vehicles:
                x, y, w, h = v["bbox"]["x"], v["bbox"]["y"], v["bbox"]["w"], v["bbox"]["h"]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                # Change your cv2.putText line to include the speed:
                label = f"{v['class']} {v['vehicle_id']} {calculated_speed}km/h"
                cv2.putText(frame, label, (x, y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            cv2.imshow(f"B1 Edge - {camera_id}", frame)
            
            # Press 'q' on your keyboard to quit the video window
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print(json.dumps({"level": "info", "message": "Shutting down B1 edge node gracefully."}))
    finally:
        # Always release the camera hardware lock!
        camera.cleanup()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()