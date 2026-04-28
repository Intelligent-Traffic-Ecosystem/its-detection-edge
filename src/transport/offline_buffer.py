import sqlite3
import json
import logging
import os

class OfflineBuffer:
    def __init__(self, db_path="data/offline_buffer.db"):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
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

    def store(self, event):
        """Saves a JSON event to the local database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO events (payload) VALUES (?)", (json.dumps(event),))
            self.conn.commit()
            logging.debug("Event stored in offline buffer.")
        except Exception as e:
            logging.error(f"Failed to store event in buffer: {e}")

    def fetch_batch(self, limit=10):
        """Fetches a batch of events from the buffer."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, payload FROM events ORDER BY id ASC LIMIT ?", (limit,))
        return cursor.fetchall()

    def delete_batch(self, ids):
        """Deletes processed events from the buffer."""
        if not ids:
            return
        cursor = self.conn.cursor()
        placeholders = ','.join(['?'] * len(ids))
        cursor.execute(f"DELETE FROM events WHERE id IN ({placeholders})", ids)
        self.conn.commit()

    def count(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events")
        return cursor.fetchone()[0]

    def close(self):
        self.conn.close()
