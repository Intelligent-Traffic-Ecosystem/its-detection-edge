import sqlite3
import json
import os

class OfflineBuffer:
    def __init__(self):
        """
        Initializes the local SQLite database. 
        Unlike document databases, SQLite uses a single file to store relational tables.
        """
        # Pull the DB path from the .env file, default to 'buffer.db' locally
        self.db_path = os.getenv("BUFFER_DB_PATH", "buffer.db")
        
        # Requirement NFR-04: Max capacity of 50,000 events
        self.max_capacity = 50000 
        self._init_db()

    def _init_db(self):
        """Creates the events table if it doesn't already exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # We store the payload as a raw JSON string to keep things simple
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
            ''')
            conn.commit()

    def save_event(self, event_dict):
        """Saves a single JSON event to the database when Kafka is down."""
        # Enforce the 50,000 event limit to prevent the Pi's storage from filling up
        if self.get_count() >= self.max_capacity:
            print("Warning: Offline buffer full! Dropping oldest event.")
            self._delete_oldest()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO events (payload) VALUES (?)', (json.dumps(event_dict),))
            conn.commit()

    # Aliases for Kafka producer compatibility
    def store(self, event_dict):
        self.save_event(event_dict)

    def count(self):
        return self.get_count()

    def get_count(self):
        """Returns the current number of saved events."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM events')
            return cursor.fetchone()[0]

    def _delete_oldest(self):
        """Deletes the oldest row to make room for new ones (FIFO order)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM events WHERE id = (SELECT MIN(id) FROM events)')
            conn.commit()

    def fetch_batch(self, batch_size=100, limit=None):
        """
        Gets a batch of events to replay once Kafka is back online.
        Requirement FR-14: Must be in FIFO (First In, First Out) order.
        """
        if limit is not None:
            batch_size = limit
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # ASC order ensures we get the oldest events first
            cursor.execute('SELECT id, payload FROM events ORDER BY id ASC LIMIT ?', (batch_size,))
            return cursor.fetchall() # Returns a list of tuples: (id, payload_string)

    def delete_batch(self, ids):
        """Deletes events from the DB *after* they are successfully sent to Kafka."""
        if not ids: 
            return
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Creates a string of question marks for the SQL query, like "?,?,?"
            placeholders = ','.join('?' * len(ids))
            cursor.execute(f'DELETE FROM events WHERE id IN ({placeholders})', ids)
            conn.commit()

    
