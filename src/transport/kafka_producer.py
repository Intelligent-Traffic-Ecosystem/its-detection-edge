import json
import logging
import time
from kafka import KafkaProducer

class TrafficKafkaProducer:
    def __init__(self, bootstrap_servers, topic, offline_buffer=None, reconnect_interval=10, enabled=True):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.buffer = offline_buffer
        self.producer = None
        self.reconnect_interval = reconnect_interval
        self.last_connect_attempt = 0
        self.last_buffer_log = 0
        self.enabled = enabled

        if self.enabled:
            self._connect()
        else:
            logging.info("Kafka disabled; events will be written to the local offline buffer.")

    def _connect(self, force=False):
        now = time.time()
        if not force and now - self.last_connect_attempt < self.reconnect_interval:
            return

        self.last_connect_attempt = now
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                retries=3,
                request_timeout_ms=3000,
                api_version_auto_timeout_ms=2000,
                max_block_ms=2000,
            )
            logging.info("Connected to Kafka successfully.")
        except Exception as e:
            logging.warning(f"Kafka broker unavailable: {e}")
            self.producer = None

    def send_event(self, event_data):
        """Attempts to send event to Kafka, falls back to buffer on failure."""
        if not self.enabled:
            if self.buffer:
                self.buffer.store(event_data)
            return

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
            self._log_buffering_status(e)
            self.producer = None
            if self.buffer:
                self.buffer.store(event_data)

    def _log_buffering_status(self, error):
        now = time.time()
        if now - self.last_buffer_log < self.reconnect_interval:
            return

        buffered_count = self.buffer.count() if self.buffer else 0
        logging.warning(
            "Kafka unavailable; buffering events locally. buffered_events=%s reason=%s",
            buffered_count,
            error,
        )
        self.last_buffer_log = now

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

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()
