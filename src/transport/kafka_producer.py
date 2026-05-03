import json
import logging
import os
from kafka import KafkaProducer

class TrafficKafkaProducer:
    def __init__(self, bootstrap_servers, topic, offline_buffer=None):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.buffer = offline_buffer
        self.producer = None
        self._connect()

    def _connect(self):
        try:
            producer_config = {
                "bootstrap_servers": self.bootstrap_servers,
                "value_serializer": lambda v: json.dumps(v).encode('utf-8'),
                "retries": 3,
                "request_timeout_ms": 5000,
            }

            security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL")
            if security_protocol:
                producer_config["security_protocol"] = security_protocol

            sasl_mechanism = os.getenv("KAFKA_SASL_MECHANISM")
            sasl_username = os.getenv("KAFKA_USERNAME")
            sasl_password = os.getenv("KAFKA_PASSWORD")
            if sasl_mechanism and sasl_username and sasl_password:
                producer_config["sasl_mechanism"] = sasl_mechanism
                producer_config["sasl_plain_username"] = sasl_username
                producer_config["sasl_plain_password"] = sasl_password

            ssl_cafile = os.getenv("KAFKA_SSL_CA")
            if ssl_cafile:
                producer_config["ssl_cafile"] = ssl_cafile

            self.producer = KafkaProducer(**producer_config)
            logging.info("Connected to Kafka successfully.")
        except Exception as e:
            logging.error(f"Failed to connect to Kafka: {e}")
            self.producer = None

    def send_event(self, event_data):
        """Attempts to send event to Kafka, falls back to buffer on failure."""
        if self.producer is None:
            self._connect()

        try:
            if self.producer:
                # Synchronous send for edge reliability (or use callback)
                future = self.producer.send(self.topic, value=event_data)
                future.get(timeout=2)
                logging.info(f"Event sent to Kafka topic: {self.topic}")
                
                # If we have a buffer, try to flush it now that we're connected
                if self.buffer and self.buffer.count() > 0:
                    self._flush_buffer()
            else:
                raise Exception("Producer not initialized")
        except Exception as e:
            logging.warning(f"Kafka send failed, storing in offline buffer: {e}")
            if self.buffer:
                self.buffer.store(event_data)

    def _flush_buffer(self):
        """Sends buffered events to Kafka when connection is restored."""
        logging.info("Flushing offline buffer...")
        batch = self.buffer.fetch_batch(limit=50)
        sent_ids = []
        
        for record_id, payload in batch:
            try:
                event = json.loads(payload)
                future = self.producer.send(self.topic, value=event)
                future.get(timeout=1)
                sent_ids.append(record_id)
            except Exception as e:
                logging.error(f"Failed to flush buffered event {record_id}: {e}")
                break # Stop flushing if connection drops again
                
        if sent_ids:
            self.buffer.delete_batch(sent_ids)
            logging.info(f"Successfully flushed {len(sent_ids)} events from buffer.")
