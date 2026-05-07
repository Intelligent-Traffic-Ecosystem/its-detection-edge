import os
import json
import logging
import ssl
from kafka import KafkaProducer
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

def diagnostic():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    topic = os.getenv("KAFKA_TOPIC")
    username = os.getenv("KAFKA_USERNAME")
    password = os.getenv("KAFKA_PASSWORD")

    protocols = ["SASL_SSL", "SASL_PLAINTEXT"]
    
    for protocol in protocols:
        print(f"\n--- Testing Protocol: {protocol} ---")
        try:
            kafka_kwargs = {
                "bootstrap_servers": bootstrap_servers,
                "security_protocol": protocol,
                "sasl_mechanism": "PLAIN",
                "sasl_plain_username": username,
                "sasl_plain_password": password,
                "value_serializer": lambda v: json.dumps(v).encode('utf-8'),
                "api_version": (2, 5, 0),
                "request_timeout_ms": 5000,
            }
            
            if protocol == "SASL_SSL":
                # Create a context that doesn't verify certs for the diagnostic
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                kafka_kwargs["ssl_context"] = context

            producer = KafkaProducer(**kafka_kwargs)
            print(f"Connection Success with {protocol}!")
            
            test_event = {"test": "diagnostic", "protocol": protocol}
            future = producer.send(topic, value=test_event)
            record_metadata = future.get(timeout=10)
            print(f"Message delivered to {record_metadata.topic} at offset {record_metadata.offset}")
            producer.close()
            return # Exit if success
        except Exception as e:
            print(f"Failed with {protocol}: {e}")

if __name__ == "__main__":
    diagnostic()
