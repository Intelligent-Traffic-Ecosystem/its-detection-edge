import os
import logging
import time
from confluent_kafka import Producer
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

def delivery_report(err, msg):
    if err is not None:
        logging.error(f"Message delivery failed: {err}")
    else:
        logging.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def diagnostic():
    load_dotenv()
    
    conf = {
        'bootstrap.servers': os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
        'security.protocol': os.getenv("KAFKA_SECURITY_PROTOCOL"),
        'sasl.mechanism': os.getenv("KAFKA_SASL_MECHANISM"),
        'sasl.username': os.getenv("KAFKA_USERNAME"),
        'sasl.password': os.getenv("KAFKA_PASSWORD"),
        'client.id': 'diagnostic-confluent'
    }
    
    print(f"--- Confluent-Kafka Diagnostic ---")
    print(f"Conf: {conf}")
    
    try:
        producer = Producer(conf)
        
        topic = os.getenv("KAFKA_TOPIC")
        producer.produce(topic, key="test-key", value="test-payload", callback=delivery_report)
        
        print(f"Waiting for delivery confirmation (10s)...")
        producer.flush(10)
        
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    diagnostic()
