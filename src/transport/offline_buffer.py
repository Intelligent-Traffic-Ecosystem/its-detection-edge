import sqlite3
import json
import threading
import logging

class OfflineBuffer:
    def __init__(self):
        """
        Initializes the local SQLite database. 
        Unlike document databases, SQLite uses a single file to store relational tables.
        """
        # Pull the DB path from the .env file, default to 'buffer.db' locally
        self.db_path = os.getenv("BUFFER_DB_PATH", "buffer.db")
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def _insert_payload_text(self, payload_text):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO events (payload) VALUES (?)", (payload_text,))
            self.conn.commit()

    def store(self, event):
        """Saves a JSON event to the local database."""
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO events (payload) VALUES (?)", (json.dumps(event),))
                self.conn.commit()
            logging.info("Event stored in offline buffer.")
        except Exception as e:
            logging.error(f"Failed to store event in buffer: {e}")

    def save(self, event_bytes):
        """Saves a pre-serialized event payload to the local database."""
        try:
            if isinstance(event_bytes, bytes):
                payload_text = event_bytes.decode("utf-8", errors="replace")
            elif isinstance(event_bytes, str):
                payload_text = event_bytes
            else:
                payload_text = json.dumps(event_bytes)
            self._insert_payload_text(payload_text)
            logging.info("Event stored in offline buffer.")
        except Exception as e:
            logging.error(f"Failed to store event in buffer: {e}")

    def fetch_batch(self, limit=10):
        """Fetches a batch of events from the buffer."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, payload FROM events ORDER BY id ASC LIMIT ?", (limit,))
            return cursor.fetchall()

    def delete_batch(self, ids):
        """Deletes events from the DB *after* they are successfully sent to Kafka."""
        if not ids: 
            return
        with self._lock:
            cursor = self.conn.cursor()
            placeholders = ','.join(['?'] * len(ids))
            cursor.execute(f"DELETE FROM events WHERE id IN ({placeholders})", ids)
            self.conn.commit()

    def replay(self, producer, limit=50):
        """Replays buffered events through a producer when connectivity returns."""
        batch = self.fetch_batch(limit=limit)
        if not batch:
            return

        sent_ids = []
        for record_id, payload in batch:
            try:
                if hasattr(producer, "publish"):
                    producer.publish(payload.encode("utf-8"))
                elif hasattr(producer, "send_event"):
                    producer.send_event(json.loads(payload))
                else:
                    raise AttributeError("Producer missing publish/send_event")
                sent_ids.append(record_id)
            except Exception as e:
                logging.error(f"Failed to replay buffered event {record_id}: {e}")
                break

        if sent_ids:
            self.delete_batch(sent_ids)
            logging.info(f"Successfully flushed {len(sent_ids)} events from buffer.")

    def count(self):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events")
            return cursor.fetchone()[0]
