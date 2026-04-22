import cv2
import threading
import time
import logging

class CameraStream:
    def __init__(self, camera_url, retry_interval=5):
        self.camera_url = camera_url
        self.retry_interval = retry_interval
        self.cap = None
        self.frame = None
        self.stopped = False
        self.lock = threading.Lock()
        self.is_connected = False

    def start(self):
        """Starts the background thread for frame capture."""
        thread = threading.Thread(target=self._update, daemon=True)
        thread.start()
        return self

    def _update(self):
        """Internal thread loop for continuous frame reading."""
        while not self.stopped:
            if not self.is_connected or self.cap is None or not self.cap.isOpened():
                self._connect()
                if not self.is_connected:
                    time.sleep(self.retry_interval)
                    continue

            success, frame = self.cap.read()
            if success:
                with self.lock:
                    self.frame = frame
            else:
                logging.warning("Failed to grab frame. Reconnecting...")
                self.is_connected = False
                time.sleep(0.1)

    def _connect(self):
        """Attempts to open the video capture stream."""
        logging.info(f"Connecting to camera: {self.camera_url}")
        if self.cap:
            self.cap.release()
            
        self.cap = cv2.VideoCapture(self.camera_url)
        if self.cap.isOpened():
            self.is_connected = True
            logging.info("Camera connected successfully.")
        else:
            self.is_connected = False
            logging.error("Failed to connect to camera.")

    def get_frame(self):
        """Returns the latest captured frame."""
        with self.lock:
            return self.frame

    def stop(self):
        """Stops the capture thread and releases resources."""
        self.stopped = True
        if self.cap:
            self.cap.release()
