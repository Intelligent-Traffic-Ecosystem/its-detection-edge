import cv2
import json
import argparse
import sys
import numpy as np
import os

# Global state
points = []
lanes = []
calibration_points = []
mode = "lanes"  # 'lanes' or 'calibration'
current_lane_id = 1

def draw_instructions(img):
    img_copy = img.copy()
    if mode == "lanes":
        cv2.putText(img_copy, f"Draw Lane {current_lane_id}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(img_copy, "Click 4 points, press 'n' for next lane, 'd' for distance calib", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Draw current points
        for p in points:
            cv2.circle(img_copy, p, 5, (0, 0, 255), -1)
        if len(points) > 1:
            cv2.polylines(img_copy, [np.array(points)], False, (0, 0, 255), 2)
            
    elif mode == "calibration":
        cv2.putText(img_copy, "Distance Calibration", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(img_copy, "Click 2 points for a known distance. Press 'Enter' when done.", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        for p in calibration_points:
            cv2.circle(img_copy, p, 5, (255, 0, 0), -1)
        if len(calibration_points) == 2:
            cv2.line(img_copy, calibration_points[0], calibration_points[1], (255, 0, 0), 2)

    # Draw saved lanes
    for lane in lanes:
        cv2.polylines(img_copy, [np.array(lane["polygon"])], True, (0, 255, 0), 2)
        # put lane id at first point
        if len(lane["polygon"]) > 0:
            cv2.putText(img_copy, lane["id"], lane["polygon"][0], cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    return img_copy

def mouse_callback(event, x, y, flags, param):
    global points, calibration_points
    if event == cv2.EVENT_LBUTTONDOWN:
        if mode == "lanes":
            points.append((x, y))
        elif mode == "calibration":
            if len(calibration_points) < 2:
                calibration_points.append((x, y))

def main():
    global mode, points, current_lane_id, lanes, calibration_points

    parser = argparse.ArgumentParser(description="Calibration Tool for ITS")
    parser.add_argument("--image", help="Path to sample image frame. If omitted, uses webcam.", default=None)
    args = parser.parse_args()

    frame = None
    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"Error: Could not read image {args.image}")
            sys.exit(1)
    else:
        print("No image provided. Capturing snapshot from webcam...")
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            print("Error: Could not capture from webcam.")
            sys.exit(1)

    cv2.namedWindow("Calibration")
    cv2.setMouseCallback("Calibration", mouse_callback)

    while True:
        display = draw_instructions(frame)
        cv2.imshow("Calibration", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('n') and mode == "lanes":
            if len(points) >= 3:
                lanes.append({
                    "id": f"lane_{current_lane_id}",
                    "polygon": points.copy()
                })
                points = []
                current_lane_id += 1
            else:
                print("Need at least 3 points for a polygon!")
        elif key == ord('d') and mode == "lanes":
            mode = "calibration"
        elif key == ord('c'):
            if mode == "lanes":
                points = []
            elif mode == "calibration":
                calibration_points = []
        elif key == 13: # Enter key
            if mode == "calibration" and len(calibration_points) == 2:
                break

    cv2.destroyAllWindows()

    pixels_to_meters = 0.05
    if len(calibration_points) == 2:
        try:
            real_dist = float(input("Enter the real-world distance between the two points in meters: "))
            pixel_dist = np.sqrt((calibration_points[0][0] - calibration_points[1][0])**2 + (calibration_points[0][1] - calibration_points[1][1])**2)
            pixels_to_meters = real_dist / pixel_dist
            print(f"Calculated pixels_to_meters: {pixels_to_meters:.5f}")
        except ValueError:
            print("Invalid input. Using default pixels_to_meters: 0.05")

    os.makedirs("config", exist_ok=True)
    out_data = {
        "lanes": lanes,
        "pixels_to_meters": pixels_to_meters
    }
    with open("config/lanes.json", "w") as f:
        json.dump(out_data, f, indent=4)
    print("Saved to config/lanes.json successfully!")

if __name__ == "__main__":
    main()
