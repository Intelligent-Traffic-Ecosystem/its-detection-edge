import json
import logging
import os
import time

try:
    from confluent_kafka import Producer, KafkaException
except Exception:
    Producer = None
    KafkaException = Exception

from kafka import KafkaProducer

TOPIC = os.getenv("KAFKA_TOPIC", "traffic.events.raw")


def _default_producer_config():
    brokers = (
        os.getenv("KAFKA_BROKERS")
        or os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        or "localhost:9092"
    )
    return {
        "bootstrap.servers": brokers,
        "acks": "all",
        "linger.ms": 5,
        "retries": 3,
        "retry.backoff.ms": 100,
        "socket.timeout.ms": 2000,
    }


def build_event(camera_id, vehicle_id, cls, confidence, bbox, centroid, speed_kmh, lane_id):
    now = time.time()
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(now)) + f"{int(now % 1 * 1000):03d}Z"
    return json.dumps(
        {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "vehicle_id": vehicle_id,
            "class": cls,
            "confidence": round(confidence, 3),
            "bbox": bbox,
            "centroid": centroid,
            "speed_kmh": round(speed_kmh, 1),
            "lane_id": lane_id,
        }
    ).encode("utf-8")


class TrafficProducer:
    def __init__(self, config=None, buffer=None, topic=None):
        if Producer is None:
            raise ImportError(
                "confluent-kafka is required for TrafficProducer. Install confluent-kafka."
            )
        self.producer = Producer(config or _default_producer_config())
        self.buffer = buffer
        self.topic = topic or TOPIC
        self._connected = True

    @property
    def connected(self):
        return self._connected

    def _on_delivery(self, err, msg):
        if err:
            self._connected = False
            logging.warning("Kafka delivery failed: %s", err)
        else:
            self._connected = True

    def _buffer_event(self, event_bytes):
        if not self.buffer:
            return
        if hasattr(self.buffer, "save"):
            self.buffer.save(event_bytes)
            return
        if hasattr(self.buffer, "store"):
            try:
                payload = json.loads(event_bytes.decode("utf-8"))
            except Exception:
                payload = {"raw": event_bytes.decode("utf-8", errors="replace")}
            self.buffer.store(payload)

    def publish(self, event_bytes: bytes):
        try:
            self.producer.produce(
                self.topic,
                value=event_bytes,
                on_delivery=self._on_delivery,
            )
            self.producer.poll(0)
        except (KafkaException, BufferError) as exc:
            self._connected = False
            logging.warning("Kafka produce failed, buffering event: %s", exc)
            self._buffer_event(event_bytes)

    def flush(self):
        self.producer.flush(timeout=0.4)

class TrafficKafkaProducer:
    def __init__(self, bootstrap_servers, topic, offline_buffer=None, reconnect_interval=10, enabled=True):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.buffer = offline_buffer
        self.producer = None
        self._confluent = None
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
            from confluent_kafka import Producer as ConfluentProducer
            conf = {
                'bootstrap.servers': self.bootstrap_servers,
                'security.protocol': os.getenv('KAFKA_SECURITY_PROTOCOL', 'SASL_PLAINTEXT'),
                'sasl.mechanisms': os.getenv('KAFKA_SASL_MECHANISM', 'PLAIN'),
                'sasl.username': os.getenv('KAFKA_USERNAME', 'its-b1-producer'),
                'sasl.password': os.getenv('KAFKA_PASSWORD', 'ITS@B1prod2026'),
                'client.id': 'its-edge-b1',
            }
            self._confluent = ConfluentProducer(conf)
            self.producer = True  # flag: connected
            logging.info("Connected to Kafka successfully.")
        except Exception as e:
            logging.warning(f"Kafka broker unavailable: {e}")
            self._confluent = None
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
            if self._confluent:
                self._confluent.produce(
                    self.topic,
                    value=json.dumps(event_data).encode('utf-8')
                )
                self._confluent.poll(0)
                
                # If we have a buffer, try to flush it now that we're connected
                if self.buffer and self.buffer.count() > 0:
                    self._flush_buffer()
            else:
                raise Exception("Producer not initialized")
        except Exception as e:
            self._log_buffering_status(e)
            self.producer = None
            self._confluent = None
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
                self._confluent.produce(self.topic, value=payload)
                self._confluent.poll(0)
                sent_ids.append(record_id)
            except Exception as e:
                logging.error(f"Failed to flush buffered event {record_id}: {e}")
                break # Stop flushing if connection drops again
                
        if sent_ids:
            self.buffer.delete_batch(sent_ids)
            logging.info(f"Successfully flushed {len(sent_ids)} events from buffer.")

    def close(self):
        if self._confluent:
            self._confluent.flush()
        self.producer = None
        self._confluent = None
