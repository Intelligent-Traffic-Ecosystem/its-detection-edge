import math
import time


class SpeedCalculator:
    def __init__(self, pixels_to_meters=0.045, video_fps=25, frame_skip=3, pixel_to_metre=None):
        """
        pixels_to_meters: Calibration ratio from pixels to real-world meters.
        pixel_to_metre is accepted for backward compatibility with older code.
        """
        if pixel_to_metre is not None:
            pixels_to_meters = pixel_to_metre

        self.pixels_to_meters = pixels_to_meters
        self.time_between_frames = (1.0 / video_fps) * max(1, frame_skip)
        self.history = {}

    def _extract_centroid(self, bbox):
        if isinstance(bbox, dict):
            if {"x", "y", "w", "h"}.issubset(bbox):
                return {
                    "x": float(bbox["x"] + (bbox["w"] / 2.0)),
                    "y": float(bbox["y"] + bbox["h"]),
                }
            if {"x", "y"}.issubset(bbox):
                return {"x": float(bbox["x"]), "y": float(bbox["y"])}

        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            x1, y1, x2, y2 = bbox[:4]
            return {
                "x": float((x1 + x2) / 2.0),
                "y": float(y2),
            }

        raise ValueError("bbox must be a list [x1, y1, x2, y2] or a bbox dict")

    def calculate_speed(self, vehicle_id, bbox, timestamp=None):
        current_centroid = self._extract_centroid(bbox)
        current_x = current_centroid["x"]
        current_y = current_centroid["y"]
        speed_kmh = 0.0

        if vehicle_id in self.history:
            prev_data = self.history[vehicle_id]
            prev_x = prev_data["centroid"]["x"]
            prev_y = prev_data["centroid"]["y"]
            prev_timestamp = prev_data["timestamp"]

            pixel_distance = math.hypot(current_x - prev_x, current_y - prev_y)
            elapsed_seconds = None
            if timestamp is not None and prev_timestamp is not None:
                elapsed_seconds = timestamp - prev_timestamp
            if not elapsed_seconds or elapsed_seconds <= 0:
                elapsed_seconds = self.time_between_frames

            if elapsed_seconds > 0:
                real_distance_meters = pixel_distance * self.pixels_to_meters
                speed_ms = real_distance_meters / elapsed_seconds
                speed_kmh = speed_ms * 3.6

        self.history[vehicle_id] = {
            "centroid": {"x": current_x, "y": current_y},
            "timestamp": timestamp if timestamp is not None else time.time(),
        }

        return round(speed_kmh, 1)

    def clear_old_tracks(self, active_track_ids):
        active_ids = set(active_track_ids)
        self.history = {track_id: data for track_id, data in self.history.items() if track_id in active_ids}

    def estimate_speed(self, vehicle_id, current_centroid):
        return self.calculate_speed(vehicle_id, current_centroid, time.time())


SpeedEstimator = SpeedCalculator