import os
import time
import json
import logging
import threading
from datetime import datetime, timezone
import cv2
import numpy as np
from dotenv import load_dotenv

from src.capture.camera import CameraStream
from src.ml.detector import TrafficDetector
from src.analytics.enricher import LaneEnricher
from src.analytics.speed import SpeedCalculator
from src.transport.kafka_producer import TrafficKafkaProducer
from src.transport.offline_buffer import OfflineBuffer
from src.api.server import DETECTION_COUNT, start_api_server

# Configure logging. force=True keeps output visible when imported libraries
# configure logging before this module starts.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', force=True)
logging.getLogger("kafka").setLevel(logging.WARNING)

def main():
    load_dotenv()
    
    # Configuration
    camera_id = os.getenv("CAMERA_ID", "cam_01")
    camera_url = os.getenv("CAMERA_URL", "tests/tst.mp4")
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_topic = os.getenv("KAFKA_TOPIC", "traffic.events.raw")
    model_path = os.getenv("MODEL_PATH", "yolov8n.pt")
    confidence = float(os.getenv("DETECTION_CONFIDENCE", "0.4"))
    tracker_config = os.getenv("TRACKER_CONFIG", "bytetrack.yaml")
    frame_skip = int(os.getenv("FRAME_SKIP", "2"))
    pixels_to_meters = float(os.getenv("PIXELS_TO_METERS", "0.05"))
    status_interval = float(os.getenv("STATUS_INTERVAL_SECONDS", "5"))
    log_detections = os.getenv("LOG_DETECTIONS", "false").lower() == "true"
    kafka_enabled = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
    display_video = os.getenv("DISPLAY_VIDEO", "false").lower() == "true"
    draw_lanes = os.getenv("DRAW_LANES", "true").lower() == "true"
    
    # Load lane config
    with open("config/lanes.json", "r") as f:
        lanes_config = json.load(f)
    
    # Initialize components
    logging.info("Initializing ITS Detection Edge Layer...")
    logging.info(
        "Config: camera_id=%s camera_url=%s model=%s confidence=%.2f frame_skip=%s display_video=%s draw_lanes=%s kafka_enabled=%s kafka=%s topic=%s",
        camera_id,
        camera_url,
        model_path,
        confidence,
        frame_skip,
        display_video,
        draw_lanes,
        kafka_enabled,
        kafka_servers,
        kafka_topic,
    )

    logging.info("Loading YOLO detector...")
    detector = TrafficDetector(
        model_path=model_path,
        confidence=confidence,
        tracker_config=tracker_config,
        frame_skip=frame_skip,
    )

    logging.info("Starting camera stream...")
    stream = CameraStream(camera_url, frame_skip=frame_skip).start()

    logging.info("Loading lane enrichment and speed modules...")
    enricher = LaneEnricher(lanes_config)
    speed_calc = SpeedCalculator(pixels_to_meters=pixels_to_meters)

    logging.info("Opening offline buffer and Kafka producer...")
    buffer = OfflineBuffer()
    producer = TrafficKafkaProducer(kafka_servers, kafka_topic, buffer, enabled=kafka_enabled)
    
    # Start API server in background thread
    threading.Thread(target=start_api_server, daemon=True).start()
    
    logging.info(f"Processing started for camera: {camera_id}")

    frames_seen = 0
    detections_seen = 0
    last_status_time = time.time()

    try:
        while True:
            frame = stream.get_frame()
            if frame is None:
                if time.time() - last_status_time >= status_interval:
                    logging.info("Waiting for frames from %s...", camera_url)
                    last_status_time = time.time()
                time.sleep(0.01)
                continue

            frames_seen += 1

            # 1. Detect and Track
            timestamp = time.time()
            timestamp_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            tracked_objects = detector.detect_and_track(frame)
            detections_seen += len(tracked_objects)
            if tracked_objects:
                DETECTION_COUNT.inc(len(tracked_objects))
            
            # 2. Enrich and Calculate Metrics
            current_ids = []
            for obj in tracked_objects:
                current_ids.append(obj["id"])
                
                # Map to lane
                obj["lane_id"] = enricher.map_to_lane(obj["bbox"])
                
                # Calculate speed
                obj["speed_kmh"] = speed_calc.calculate_speed(obj["id"], obj["bbox"], timestamp)
                
                # 3. Build SRS-style message and send
                event = {
                    "camera_id": camera_id,
                    "timestamp": timestamp_iso,
                    "frame_id": obj["frame_id"],
                    "vehicle_id": obj["vehicle_id"],
                    "class": obj["class"],
                    "confidence": obj["confidence"],
                    "bbox": obj["bbox_xywh"],
                    "centroid": obj["centroid"],
                    "lane_id": obj["lane_id"],
                    "speed_estimate": obj["speed_kmh"],
                }
                if log_detections:
                    logging.info(
                        "Detection: vehicle_id=%s class=%s confidence=%.2f lane=%s speed=%.2f km/h",
                        event["vehicle_id"],
                        event["class"],
                        event["confidence"],
                        event["lane_id"],
                        event["speed_estimate"],
                    )
                producer.send_event(event)

            # Cleanup old tracking history
            speed_calc.clear_old_tracks(current_ids)

            if display_video:
                annotated_frame = draw_detections(frame, tracked_objects, lanes_config if draw_lanes else None)
                cv2.imshow("ITS Detection Edge - press q to quit", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logging.info("Display quit requested.")
                    break

            if time.time() - last_status_time >= status_interval:
                logging.info(
                    "Status: frames=%s total_detections=%s active_tracks=%s buffered_events=%s",
                    frames_seen,
                    detections_seen,
                    len(current_ids),
                    buffer.count(),
                )
                last_status_time = time.time()
            
            # Control frame rate for edge processing
            time.sleep(0.05) 
            
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        stream.stop()
        if display_video:
            cv2.destroyAllWindows()
        producer.close()
        buffer.close()

def draw_detections(frame, tracked_objects, lanes_config=None):
    annotated = frame.copy()
    green = (0, 255, 0)
    black = (0, 0, 0)
    lane_color = (255, 180, 0)

    if lanes_config:
        annotated = draw_lanes_overlay(annotated, lanes_config, lane_color)

    for obj in tracked_objects:
        x1, y1, x2, y2 = [int(value) for value in obj["bbox"]]
        lane_id = obj.get("lane_id", "unknown")
        vehicle_type = obj.get("class", "vehicle")
        label = f'{obj["vehicle_id"]} {vehicle_type} {lane_id} {obj["speed_kmh"]:.1f} km/h'

        cv2.rectangle(annotated, (x1, y1), (x2, y2), green, 2)

        text_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        text_w, text_h = text_size
        label_y = max(y1 - 8, text_h + baseline + 4)
        cv2.rectangle(
            annotated,
            (x1, label_y - text_h - baseline - 4),
            (x1 + text_w + 8, label_y + baseline),
            green,
            -1,
        )
        cv2.putText(
            annotated,
            label,
            (x1 + 4, label_y - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            black,
            2,
            cv2.LINE_AA,
        )

    return annotated


def draw_lanes_overlay(frame, lanes_config, lane_color):
    overlay = frame.copy()
    lanes = lanes_config.get("lanes", [])

    for lane in lanes:
        polygon = lane.get("polygon", [])
        if len(polygon) < 3:
            continue

        points = np.array(polygon, dtype=np.int32)
        cv2.fillPoly(overlay, [points], lane_color)

    frame = cv2.addWeighted(overlay, 0.18, frame, 0.82, 0)

    for lane in lanes:
        polygon = lane.get("polygon", [])
        if len(polygon) < 3:
            continue

        points = np.array(polygon, dtype=np.int32)
        cv2.polylines(frame, [points], isClosed=True, color=lane_color, thickness=2)
        label_x, label_y = polygon[0]
        label = str(lane.get("id", "lane"))
        cv2.putText(
            frame,
            label,
            (int(label_x), max(int(label_y) - 8, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            lane_color,
            2,
            cv2.LINE_AA,
        )

    return frame


if __name__ == "__main__":
    main()
