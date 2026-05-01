import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import cv2


class LaneCalibrator:
    def __init__(self, frame, output_path, camera_id):
        self.frame = frame
        self.output_path = output_path
        self.camera_id = camera_id
        self.current_points = []
        self.lanes = []

    def run(self):
        window_name = "Lane calibration"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self._handle_mouse)

        print("Left click: add point")
        print("n: save current polygon as next lane")
        print("u: undo last point")
        print("s: write lanes JSON")
        print("q: quit")

        while True:
            canvas = self._draw_overlay()
            cv2.imshow(window_name, canvas)
            key = cv2.waitKey(20) & 0xFF

            if key == ord("n"):
                self._save_current_lane()
            elif key == ord("u"):
                if self.current_points:
                    self.current_points.pop()
            elif key == ord("s"):
                self._save_current_lane()
                self._write_config()
                break
            elif key == ord("q"):
                break

        cv2.destroyAllWindows()

    def _handle_mouse(self, event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_points.append([x, y])

    def _save_current_lane(self):
        if not self.current_points:
            return

        if len(self.current_points) < 3:
            print("A lane polygon needs at least 3 points.")
            return

        lane_id = f"lane_{len(self.lanes) + 1}"
        self.lanes.append({
            "id": lane_id,
            "polygon": self.current_points.copy(),
            "direction": "unknown",
        })
        print(f"Saved {lane_id}: {self.current_points}")
        self.current_points.clear()

    def _write_config(self):
        payload = {
            "camera_id": self.camera_id,
            "lanes": self.lanes,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {self.output_path}")

    def _draw_overlay(self):
        canvas = self.frame.copy()

        for lane in self.lanes:
            self._draw_polygon(canvas, lane["polygon"], closed=True, color=(0, 180, 0))

        self._draw_polygon(canvas, self.current_points, closed=False, color=(0, 255, 255))
        return canvas

    def _draw_polygon(self, canvas, points, closed, color):
        for point in points:
            cv2.circle(canvas, tuple(point), 4, color, -1)

        for index in range(1, len(points)):
            cv2.line(canvas, tuple(points[index - 1]), tuple(points[index]), color, 2)

        if closed and len(points) > 2:
            cv2.line(canvas, tuple(points[-1]), tuple(points[0]), color, 2)


def read_first_frame(video_source):
    cap = cv2.VideoCapture(video_source)
    try:
        success, frame = cap.read()
        if not success:
            raise RuntimeError(f"Could not read a frame from {video_source}")
        return frame
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description="Draw lane polygons on the first frame of a video/camera feed.")
    parser.add_argument("--source", default="tests/test.mp4", help="Video file, camera index, or RTSP URL.")
    parser.add_argument("--output", default="config/lanes.json", help="Path to write lane config JSON.")
    parser.add_argument("--camera-id", default=os.getenv("CAMERA_ID", "cam_01"), help="Camera ID to write into the lane config.")
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    frame = read_first_frame(source)
    LaneCalibrator(frame, Path(args.output), args.camera_id).run()


if __name__ == "__main__":
    main()
