import cv2
import os
import threading
import time
import logging
import os

class CameraStream:
    def __init__(self, camera_url, retry_interval=5, frame_skip=None):
        self.camera_url = camera_url
        self.retry_interval = retry_interval
        self.frame_skip = frame_skip if frame_skip is not None else int(os.getenv("FRAME_SKIP", "2"))
        self._frame_counter = 0
        self.cap = None
        self.frame = None
        self.stopped = False
        self.lock = threading.Lock()
        self.is_connected = False
        self.is_file_source = self._is_file_source(camera_url)
        self.read_interval = 0.0

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
                self._frame_counter += 1
                # Only update the shared frame every FRAME_SKIP frames
                if self._frame_counter % (self.frame_skip + 1) == 0:
                    with self.lock:
                        self.frame = frame
                if self.read_interval > 0:
                    time.sleep(self.read_interval)
            else:
                if self.is_file_source:
                    logging.info("Reached end of video file, replaying: %s", self.camera_url)
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

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
            self.read_interval = self._get_file_read_interval()
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

    def _is_file_source(self, camera_url):
        return isinstance(camera_url, str) and os.path.isfile(camera_url)

    def _get_file_read_interval(self):
        if not self.is_file_source:
            return 0.0

        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0:
            return min(1.0 / fps, 0.1)

        return 0.03
