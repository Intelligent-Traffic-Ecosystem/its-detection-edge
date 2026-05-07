import requests
import json

url = "https://d4y6ftdjf6.execute-api.ap-southeast-2.amazonaws.com/prod/detections"
key = "p8qzyH5tus1YGmnNEGJ6N2j9334KypOn8Qz97KmK"

headers = {
    "Content-Type": "application/json",
    "x-api-key": key
}

dummy_event = {
    "camera_id": "test_cam_01",
    "timestamp": "2026-05-04T10:00:00Z",
    "vehicle_id": "test_veh_999",
    "class": "car",
    "confidence": 0.99,
    "bbox": [100, 100, 200, 200],
    "centroid": [150, 150],
    "lane_id": 1,
    "speed_estimate": 45.5
}

print(f"Sending test event to {url}...")
try:
    response = requests.post(url, json=dummy_event, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
