import math
import time

class SpeedEstimator:
    def __init__(self, pixel_to_metre=0.045,video_fps=25, frame_skip=3):
        """
        pixel_to_metre: A calibration ratio. For example, 0.045 means 
        1 pixel on the camera screen equals 0.045 real-world meters.
        (Your Hardware Engineer will eventually provide this exact number from calibrate.py)
        """
        self.pixel_to_metre = pixel_to_metre
        
        # Calculate exactly how much video time passes between the frames we process
        self.time_between_frames = (1.0 / video_fps) * frame_skip

        # We need a memory dictionary to remember where each car was in the PREVIOUS frame
        self.history = {} 

    def estimate_speed(self, vehicle_id, current_centroid):
        current_x = current_centroid["x"]
        current_y = current_centroid["y"]
        speed_kmh = 0.0

        if vehicle_id in self.history:
            prev_data = self.history[vehicle_id]
            prev_x = prev_data["centroid"]["x"]
            prev_y = prev_data["centroid"]["y"]

            # Calculate pixel distance using the Pythagorean theorem
            pixel_distance = math.sqrt((current_x - prev_x)**2 + (current_y - prev_y)**2)
            
            # Convert pixels to real-world meters
            real_distance_meters = pixel_distance * self.pixel_to_metre
            
            # Speed = Distance / Time (Using the constant video time, not CPU time!)
            speed_ms = real_distance_meters / self.time_between_frames
            
            # Convert m/s to km/h
            speed_kmh = speed_ms * 3.6

        # Save the current position
        self.history[vehicle_id] = {
            "centroid": {"x": current_x, "y": current_y}
        }

        return round(speed_kmh, 1)