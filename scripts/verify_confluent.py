import os
import json
import logging
from confluent_kafka import Producer
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

def delivery_report(err, msg):
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')

def main():
    # Use the identified IP
    broker = "139.59.85.137:32092"
    topic = os.getenv("KAFKA_TOPIC", "traffic.events.raw")
    
    print(f"Testing with confluent-kafka to {broker}...")
    
    # Configuration
    conf = {
        'bootstrap.servers': broker,
        'client.id': 'verify-confluent',
        'acks': 'all',
        'retries': 3,
        # Try without SASL first as kafka-values.yaml suggested PLAINTEXT
    }
    
    try:
        p = Producer(conf)
        
        mock_data = {
            "camera_id": "confluent_verify",
            "timestamp": "2026-05-05T16:50:00.000Z",
            "vehicle_id": "veh_conf_001",
            "class": "car",
            "lane_id": 1,
            "speed_kmh": 55.5
        }
        
        print(f"Sending mock data to {topic}...")
        p.produce(topic, json.dumps(mock_data).encode('utf-8'), callback=delivery_report)
        
        # Wait for any outstanding messages to be delivered and delivery report
        # callbacks to be triggered.
        p.flush(timeout=10)
        print("Done.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
