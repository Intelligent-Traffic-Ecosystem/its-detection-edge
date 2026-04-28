import cv2
import json
import os
from datetime import datetime, timezone


class LaneCalibrator:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.lanes = []
        self.current_lane_id = None
        self.current_direction = None
        self.current_points = []
        self.is_drawing = False
        self.window_name = "Lane Calibration"

    def start_lane(self, lane_id, direction):
        self.current_lane_id = lane_id
        self.current_direction = direction
        self.current_points = []
        self.is_drawing = True

    def cancel_lane(self):
        self.current_lane_id = None
        self.current_direction = None
        self.current_points = []
        self.is_drawing = False

    def finalize_lane(self):
        if not self.current_lane_id or len(self.current_points) < 3:
            return False

        lane = {
            "id": self.current_lane_id,
            "polygon": self.current_points,
            "direction": self.current_direction,
        }
        self.lanes.append(lane)
        self.cancel_lane()
        return True

    def undo_point(self):
        if self.current_points:
            self.current_points.pop()

    def mouse_callback(self, event, x, y, flags, param):
        if not self.is_drawing:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_points.append([int(x), int(y)])

    def draw_overlay(self, frame):
        # Draw existing lanes
        for lane in self.lanes:
            pts = lane["polygon"]
            if len(pts) >= 2:
                for i in range(len(pts) - 1):
                    cv2.line(frame, tuple(pts[i]), tuple(pts[i + 1]), (0, 255, 0), 2)
                cv2.line(frame, tuple(pts[-1]), tuple(pts[0]), (0, 255, 0), 2)

        # Draw current lane-in-progress
        if len(self.current_points) >= 1:
            for i in range(len(self.current_points) - 1):
                cv2.line(frame, tuple(self.current_points[i]), tuple(self.current_points[i + 1]), (0, 255, 255), 2)
            for pt in self.current_points:
                cv2.circle(frame, tuple(pt), 4, (0, 255, 255), -1)

        # Instruction overlay
        instructions = [
            "Keys: n=new lane, c=close lane, u=undo point, s=save, q=quit",
            "Mouse: left click to add points",
        ]
        y = 20
        for line in instructions:
            cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y += 18

        status = ""
        if self.is_drawing:
            status = f"Drawing: {self.current_lane_id} ({self.current_direction}) - points: {len(self.current_points)}"
        else:
            status = "Press n to start a new lane"
        cv2.putText(frame, status, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def _get_capture():
    camera_type = os.getenv("CAMERA_TYPE", "usb").lower()
    camera_index = int(os.getenv("CAMERA_INDEX", 0))
    stream_url = os.getenv("CAMERA_STREAM_URL", "")

    if camera_type == "usb":
        return cv2.VideoCapture(camera_index)
    if camera_type == "ip":
        return cv2.VideoCapture(stream_url)
    raise ValueError(f"Unknown CAMERA_TYPE: {camera_type}")


def _save_lanes(output_path, camera_id, lanes):
    payload = {
        "camera_id": camera_id,
        "lanes": lanes,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    print("Calibration tool started...")
    camera_id = os.getenv("CAMERA_ID", "cam_01")
    output_path = os.getenv("LANES_CONFIG_PATH", os.path.join("config", "lanes.json"))

    cap = _get_capture()
    if not cap.isOpened():
        raise ConnectionError("Camera failed to open. Check connections or URL.")

    calibrator = LaneCalibrator(camera_id)
    cv2.namedWindow(calibrator.window_name)
    cv2.setMouseCallback(calibrator.window_name, calibrator.mouse_callback)

    while True:
        success, frame = cap.read()
        if not success:
            print("Warning: Camera stream dropped.")
            break

        preview = frame.copy()
        calibrator.draw_overlay(preview)
        cv2.imshow(calibrator.window_name, preview)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("n"):
            lane_id = input("Enter lane id (e.g., lane_1): ").strip()
            direction = input("Direction (inbound/outbound/unknown): ").strip() or "unknown"
            if lane_id:
                calibrator.start_lane(lane_id, direction)
        elif key == ord("c"):
            if not calibrator.finalize_lane():
                print("Lane needs at least 3 points to close.")
        elif key == ord("u"):
            calibrator.undo_point()
        elif key == ord("s"):
            _save_lanes(output_path, camera_id, calibrator.lanes)
            print(f"Saved lanes to {output_path}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
