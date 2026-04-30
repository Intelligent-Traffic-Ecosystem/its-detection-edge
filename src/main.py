import os
import time
import json
import logging
import threading
from dotenv import load_dotenv

from src.capture.camera import CameraStream
from src.ml.detector import TrafficDetector
from src.analytics.enricher import LaneEnricher
from src.analytics.speed import SpeedCalculator
from src.transport.kafka_producer import TrafficKafkaProducer
from src.transport.offline_buffer import OfflineBuffer
from src.api.server import start_api_server

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    load_dotenv()
    
    # Configuration
    camera_id = os.getenv("CAMERA_ID", "cam_01")
    camera_url = os.getenv("CAMERA_URL", "tests/test_video.mp4")
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_topic = os.getenv("KAFKA_TOPIC", "traffic.events.raw")
    frame_skip = int(os.getenv("FRAME_SKIP", "2"))
    
    # Load lane config
    with open("config/lanes.json", "r") as f:
        lanes_config = json.load(f)
        
    pixels_to_meters = lanes_config.get("pixels_to_meters", float(os.getenv("PIXELS_TO_METERS", "0.05")))
    
    # Initialize components
    logging.info("Initializing ITS Detection Edge Layer...")
    
    stream = CameraStream(camera_url, frame_skip=frame_skip).start()
    detector = TrafficDetector()
    enricher = LaneEnricher(lanes_config)
    speed_calc = SpeedCalculator(pixels_to_meters=pixels_to_meters)
    buffer = OfflineBuffer()
    producer = TrafficKafkaProducer(kafka_servers, kafka_topic, buffer)
    
    # Start API server in background thread
    threading.Thread(target=start_api_server, daemon=True).start()
    
    logging.info(f"Processing started for camera: {camera_id}")
    
    try:
        while True:
            frame = stream.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
                
            # 1. Detect and Track
            timestamp = time.time()
            tracked_objects = detector.detect_and_track(frame)
            
            # 2. Enrich and Calculate Metrics
            current_ids = []
            for obj in tracked_objects:
                current_ids.append(obj["id"])
                
                # Map to lane
                obj["lane_id"] = enricher.map_to_lane(obj["bbox"])
                
                # Calculate speed
                obj["speed_kmh"] = speed_calc.calculate_speed(obj["id"], obj["bbox"], timestamp)
                
                # 3. Build message and send
                event = {
                    "camera_id": camera_id,
                    "timestamp": timestamp,
                    "vehicle": {
                        "id": obj["id"],
                        "type": obj["class"],
                        "speed": obj["speed_kmh"],
                        "lane": obj["lane_id"],
                        "bbox": obj["bbox"]
                    }
                }
                producer.send_event(event)

            # Cleanup old tracking history
            speed_calc.clear_old_tracks(current_ids)
            
            # Control frame rate for edge processing
            time.sleep(0.05) 
            
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        stream.stop()

if __name__ == "__main__":
    main()
