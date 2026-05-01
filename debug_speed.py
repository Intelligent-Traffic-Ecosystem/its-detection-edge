import time
import cv2
from src.ml.detector import TrafficDetector
from src.analytics.speed import SpeedCalculator

def test_speed():
    detector = TrafficDetector(model_path="yolov8n.pt", confidence=0.4, tracker_config="bytetrack.yaml")
    speed_calc = SpeedCalculator(pixels_to_meters=0.05)
    
    cap = cv2.VideoCapture("tests/test2.mp4")
    
    for i in range(20):
        ret, frame = cap.read()
        if not ret: break
        
        timestamp = time.time()
        tracked = detector.detect_and_track(frame)
        current_ids = []
        for obj in tracked:
            speed = speed_calc.calculate_speed(obj["id"], obj["bbox"], timestamp)
            current_ids.append(obj["id"])
            if speed > 0:
                print(f"Frame {i}: ID {obj['id']} Speed {speed}")
            else:
                print(f"Frame {i}: ID {obj['id']} Speed {speed} (zero)")
                
        speed_calc.clear_old_tracks(current_ids)
        time.sleep(0.05)

test_speed()
