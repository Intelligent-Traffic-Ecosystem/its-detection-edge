import json
import logging
import time
import os
from kafka import KafkaProducer
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_mock_event(index):
    now = time.time()
    timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(now)) + f"{int(now % 1 * 1000):03d}Z"
    
    return {
        "camera_id": "verify_cam_01",
        "timestamp": timestamp_iso,
        "vehicle_id": f"veh_verify_{index:03d}",
        "class": "car",
        "confidence": 0.95,
        "bbox": {
            "x": 100 + index * 10,
            "y": 200,
            "w": 50,
            "h": 30
        },
        "centroid": {
            "x": 125 + index * 10,
            "y": 215
        },
        "lane_id": 1,
        "speed_kmh": 45.5 + index
    }

def test_connection(servers, security_protocol, username=None, password=None):
    logging.info(f"--- Testing: {servers} | {security_protocol} ---")
    
    kafka_kwargs = {
        "bootstrap_servers": servers,
        "value_serializer": lambda v: json.dumps(v).encode('utf-8'),
        "api_version": (2, 5, 0),
        "request_timeout_ms": 5000,
        "acks": "all"
    }
    
    if security_protocol == "SASL_PLAINTEXT":
        kafka_kwargs.update({
            "security_protocol": "SASL_PLAINTEXT",
            "sasl_mechanism": "PLAIN",
            "sasl_plain_username": username,
            "sasl_plain_password": password
        })
    
    try:
        producer = KafkaProducer(**kafka_kwargs)
        topic = os.getenv("KAFKA_TOPIC", "b1.edge.detections.prod")
        
        logging.info(f"Connection established. Sending 3 mock events to topic: {topic}")
        
        for i in range(1, 4):
            event = get_mock_event(i)
            future = producer.send(topic, value=event)
            # Synchronous wait for delivery
            record_metadata = future.get(timeout=10)
            logging.info(f"SUCCESS: Event {i} sent to {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}")
            time.sleep(0.5)
            
        producer.flush()
        producer.close()
        return True
    except Exception as e:
        logging.error(f"FAILED: {e}")
        return False

def main():
    load_dotenv()
    
    # Try the IPs we've identified
    ips = ["139.59.85.137:32092", "139.59.64.130:32092"]
    username = os.getenv("KAFKA_USERNAME")
    password = os.getenv("KAFKA_PASSWORD")
    
    results = []
    
    for ip in ips:
        # 1. Try SASL (as specified in credentials)
        if test_connection(ip, "SASL_PLAINTEXT", username, password):
            results.append(f"SUCCESS: {ip} with SASL")
            break # Stop if we found a working one
            
        # 2. Try Plaintext (just in case the port is open)
        if test_connection(ip, "PLAINTEXT"):
            results.append(f"SUCCESS: {ip} without SASL")
            break
            
    if not results:
        logging.error("All connection attempts failed. Please verify if your IP is allowlisted at the broker.")
    else:
        for res in results:
            print(f"\n*** {res} ***")

if __name__ == "__main__":
    main()
