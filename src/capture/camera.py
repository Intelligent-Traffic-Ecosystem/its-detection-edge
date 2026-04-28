import cv2
import os


class VideoCaptureManager:
    def __init__(self):
        """
        Pulls configuration from environment variables. 
        This keeps hardcoded values out of the code, making the DevOps engineer's job easier.
        """
        self.camera_type = os.getenv("CAMERA_TYPE", "usb").lower()
        self.camera_index = int(os.getenv("CAMERA_INDEX", 0))
        self.stream_url = os.getenv("CAMERA_STREAM_URL", "")
        self.frame_skip = int(os.getenv("FRAME_SKIP", 3))  # Process 1 in 3 frames by default
        
        self.cap = self._initialize_camera()
        self.frame_counter = 0

    def _initialize_camera(self):
        """
        Connects to either a local USB webcam (V4L2) or a network stream (RTSP/HTTP).
        """
        if self.camera_type == "usb":
            print(f"Connecting to USB Camera at /dev/video{self.camera_index}...")
            cap = cv2.VideoCapture(self.camera_index)
        elif self.camera_type == "ip":
            print(f"DEBUG: OpenCV is trying to open EXACTLY this string: '{self.stream_url}'")
            print(f"Connecting to IP Camera stream...")
            cap = cv2.VideoCapture(self.stream_url)
        else:
            raise ValueError(f"Unknown camera type: {self.camera_type}. Must be 'usb' or 'ip'.")

        if not cap.isOpened():
            raise ConnectionError("Camera failed to open. Check connections or URL.")
            
        return cap

    def get_processed_frame(self):
        """
        Continuously pulls frames from the buffer, but only returns one 
        when it meets the FRAME_SKIP interval.
        """
        while True:
            # .read() grabs the latest image from the camera sensor
            success, frame = self.cap.read()
            
            if not success:
                print("Warning: Camera stream dropped.")
                return None  # Returning None lets the main loop trigger the 5-second retry logic
                
            self.frame_counter += 1
            
            # The Modulo operator (%) checks if the counter is a multiple of the skip value
            if self.frame_counter % self.frame_skip == 0:
                
                # YOLOv8n expects a 640x480 image. Resizing it here ensures 
                # consistent processing times regardless of the original camera resolution.
                resized_frame = cv2.resize(frame, (640, 480))
                return resized_frame
                
    def cleanup(self):
        """Releases the hardware lock on the camera."""
        if self.cap:
            self.cap.release()