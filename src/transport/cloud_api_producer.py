import json
import logging
import time
import requests
from datetime import datetime, timezone

class CloudAPIProducer:
    """
    Sends detection events to a Cloud API (AWS API Gateway).
    Includes local buffering for resilience during network outages.
    """
    def __init__(self, api_url, api_key, offline_buffer=None, enabled=True):
        self.api_url = api_url
        self.api_key = api_key
        self.buffer = offline_buffer
        self.enabled = enabled
        self.timeout = 5
        self.last_buffer_log = 0
        self.log_interval = 10

        if self.enabled:
            logging.info(f"Cloud API Producer initialized. URL: {self.api_url}")
        else:
            logging.info("Cloud API Producer disabled.")

    def send_event(self, event_data):
        """
        Attempts to POST event to the Cloud API. 
        Falls back to local SQLite buffer on failure.
        """
        if not self.enabled:
            if self.buffer:
                self.buffer.store(event_data)
            return

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }

        try:
            # AWS Lambda/API Gateway often expects a list or single object
            # We send a single event here
            response = requests.post(
                self.api_url, 
                json=event_data, 
                headers=headers, 
                timeout=self.timeout
            )
            
            if response.status_code in [200, 201, 202]:
                logging.info(f"Event successfully sent to Cloud API. vehicle_id={event_data.get('vehicle_id')}")
                
                # If we have a buffer, try to flush it
                if self.buffer and self.buffer.count() > 0:
                    self._flush_buffer()
            else:
                logging.warning(f"Cloud API rejected event: {response.status_code} - {response.text}")
                self._buffer_event(event_data)
                
        except Exception as e:
            self._log_buffering_status(e)
            self._buffer_event(event_data)

    def _buffer_event(self, event_data):
        if self.buffer:
            self.buffer.store(event_data)

    def _log_buffering_status(self, error):
        now = time.time()
        if now - self.last_buffer_log < self.log_interval:
            return

        buffered_count = self.buffer.count() if self.buffer else 0
        logging.warning(
            "Cloud API unreachable; buffering events locally. buffered_events=%s reason=%s",
            buffered_count,
            error,
        )
        self.last_buffer_log = now

    def _flush_buffer(self):
        """Sends buffered events to the API when connection is restored."""
        logging.info("Flushing offline buffer to Cloud API...")
        batch = self.buffer.fetch_batch(limit=10) # Small batches for API
        sent_ids = []
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }

        for record_id, payload in batch:
            try:
                event = json.loads(payload)
                response = requests.post(
                    self.api_url, 
                    json=event, 
                    headers=headers, 
                    timeout=self.timeout
                )
                if response.status_code in [200, 201, 202]:
                    sent_ids.append(record_id)
                else:
                    logging.error(f"Failed to flush buffered event {record_id}: {response.status_code}")
                    break 
            except Exception as e:
                logging.error(f"Error flushing buffered event {record_id}: {e}")
                break
                
        if sent_ids:
            self.buffer.delete_batch(sent_ids)
            logging.info(f"Successfully flushed {len(sent_ids)} events to Cloud API.")

    def close(self):
        # No specific cleanup needed for requests
        pass
