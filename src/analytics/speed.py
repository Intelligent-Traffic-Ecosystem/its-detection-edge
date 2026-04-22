import math
import time

class SpeedCalculator:
    def __init__(self, pixels_to_meters=0.05, history_len=5):
        """
        pixels_to_meters: Conversion factor for the specific camera setup.
        history_len: Number of frames to average speed over.
        """
        self.history = {} # track_id -> [(timestamp, x, y), ...]
        self.pixels_to_meters = pixels_to_meters
        self.history_len = history_len

    def calculate_speed(self, track_id, bbox, timestamp=None):
        """
        Calculates speed in km/h based on position change.
        """
        if timestamp is None:
            timestamp = time.time()
            
        # Get bottom-center as representative point
        x = (bbox[0] + bbox[2]) / 2
        y = bbox[3]
        
        if track_id not in self.history:
            self.history[track_id] = []
            
        self.history[track_id].append((timestamp, x, y))
        
        # We need at least 2 points to calculate speed
        if len(self.history[track_id]) < 2:
            return 0.0
            
        # Limit history
        if len(self.history[track_id]) > self.history_len:
            self.history[track_id].pop(0)
            
        # Calculate speed between first and last recorded points in window
        t1, x1, y1 = self.history[track_id][0]
        t2, x2, y2 = self.history[track_id][-1]
        
        dt = t2 - t1
        if dt <= 0:
            return 0.0
            
        dx = x2 - x1
        dy = y2 - y1
        dist_px = math.sqrt(dx**2 + dy**2)
        dist_m = dist_px * self.pixels_to_meters
        
        speed_mps = dist_m / dt
        speed_kmh = speed_mps * 3.6
        
        return round(speed_kmh, 2)

    def clear_old_tracks(self, active_ids):
        """Removes tracking history for IDs no longer in view."""
        self.history = {tid: hist for tid, hist in self.history.items() if tid in active_ids}
