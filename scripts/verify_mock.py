import json
import logging
import time
import sys
import os
from kafka import KafkaProducer
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_config(ip, topic, security, username=None, password=None):
    logging.info(f"TESTING: IP={ip}, Topic={topic}, Security={security}")
    
    kwargs = {
        "bootstrap_servers": ip,
        "value_serializer": lambda v: json.dumps(v).encode('utf-8'),
        "api_version": (2, 6, 0),
        "request_timeout_ms": 10000,
        "acks": "all"
    }
    
    if security == "SASL_PLAINTEXT":
        kwargs.update({
            "security_protocol": "SASL_PLAINTEXT",
            "sasl_mechanism": "PLAIN",
            "sasl_plain_username": username,
            "sasl_plain_password": password
        })
    
    try:
        producer = KafkaProducer(**kwargs)
        
        mock_data = {
            "camera_id": "remote_verify",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "vehicle_id": "veh_001",
            "class": "car",
            "lane_id": 1,
            "speed_kmh": 65.0
        }
        
        future = producer.send(topic, value=mock_data)
        metadata = future.get(timeout=20)
        
        logging.info(f"SUCCESS! Sent to {metadata.topic} partition {metadata.partition} offset {metadata.offset}")
        producer.close()
        return True
    except Exception as e:
        logging.error(f"FAILED: {e}")
        return False

def main():
    load_dotenv()
    
    # Added the new IP found from DNS
    ips = ["209.38.127.207:32092", "209.38.127.207:9092", "139.59.85.137:32092", "139.59.64.130:32092"]
    topics = ["traffic.events.raw", "b1.edge.detections.prod"]
    username = os.getenv("KAFKA_USERNAME", "its-b1-producer")
    password = os.getenv("KAFKA_PASSWORD", "ITS@B1prod2026")
    
    for ip in ips:
        for topic in topics:
            # 1. Try Plaintext
            if test_config(ip, topic, "PLAINTEXT"):
                print(f"\n*** WORKING CONFIG: {ip} | {topic} | PLAINTEXT ***")
                return
            
            # 2. Try SASL
            if test_config(ip, topic, "SASL_PLAINTEXT", username, password):
                print(f"\n*** WORKING CONFIG: {ip} | {topic} | SASL_PLAINTEXT ***")
                return

    print("\nCould not find a working remote configuration.")

if __name__ == "__main__":
    main()
