import os
import time
import json
import logging
import threading
from dotenv import load_dotenv

from src.capture.camera import CameraStream
from src.ml.detector import TrafficDetector
from src.analytics.enricher import LaneEnricher, EventSerializer
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
    
    # Load lane config
    with open("config/lanes.json", "r") as f:
        lanes_config = json.load(f)
    
    # Initialize components
    logging.info("Initializing ITS Detection Edge Layer...")
    
    stream = CameraStream(camera_url).start()
    detector = TrafficDetector()
    enricher = LaneEnricher(lanes_config)
    serializer = EventSerializer(enricher)
    speed_calc = SpeedCalculator()
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
            if not tracked_objects:
                time.sleep(0.05)
                continue
            
            # 2. Serialize & Enrich (Developer 2 layer)
            events = serializer.serialize_batch(
                vehicles=tracked_objects,
                camera_id=camera_id,
                frame_id=0,  # TODO: Add frame counter if needed
                timestamp=timestamp
            )
            
            # 3. Calculate speed and send
            current_ids = []
            for i, obj in enumerate(tracked_objects):
                current_ids.append(obj.get("vehicle_id") or obj.get("id"))
                speed_kmh = speed_calc.calculate_speed(
                    obj.get("vehicle_id") or obj.get("id"),
                    obj.get("bbox"),
                    timestamp
                )
                events[i]["speed_estimate"] = speed_kmh
                producer.send_event(events[i])

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
