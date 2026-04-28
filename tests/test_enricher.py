#!/usr/bin/env python3
"""Quick test to verify enricher implementation."""

import sys
import os
import json
from datetime import datetime, timezone

# Add project root to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analytics.enricher import LaneEnricher, EventSerializer


def test_enricher():
    # Load config
    with open("config/lanes.json", "r") as f:
        config = json.load(f)

    # Initialize components
    enricher = LaneEnricher(config)
    serializer = EventSerializer(enricher)

    # Test single vehicle serialization
    vehicle = {
        "vehicle_id": "veh_203",
        "class": "car",
        "confidence": 0.93,
        "bbox": {"x": 412, "y": 178, "w": 82, "h": 46},
        "centroid": {"x": 50, "y": 50},  # Inside lane_1 polygon [0,0,100,0,100,100,0,100]
        "speed": 34.2
    }

    test_timestamp = datetime(2026, 4, 16, 10, 15, 23, 456000, tzinfo=timezone.utc)
    event = serializer.serialize_event(vehicle, "cam_north_approach", 18422, test_timestamp)

    print("=" * 60)
    print("Single Event Serialization Test:")
    print("=" * 60)
    print(json.dumps(event, indent=2))

    # Verify key fields
    assert event["camera_id"] == "cam_north_approach", "camera_id mismatch"
    assert event["timestamp"] == "2026-04-16T10:15:23.456Z", "timestamp format incorrect"
    assert event["frame_id"] == 18422, "frame_id mismatch"
    assert event["vehicle_id"] == "veh_203", "vehicle_id mismatch"
    assert event["class"] == "car", "class mismatch"
    assert event["confidence"] == 0.93, "confidence mismatch"
    assert event["lane_id"] == "lane_1", f"lane_id should be 'lane_1', got {event['lane_id']}"
    assert event["speed_estimate"] == 34.2, "speed_estimate mismatch"

    print("\n✓ All assertions passed!")

    # Test batch serialization
    vehicles = [vehicle, vehicle.copy()]
    vehicles[1]["vehicle_id"] = "veh_204"
    vehicles[1]["centroid"] = {"x": 150, "y": 50}  # Inside lane_2

    events = serializer.serialize_batch(vehicles, "cam_north_approach", 18423, test_timestamp)

    print("\n" + "=" * 60)
    print("Batch Serialization Test:")
    print("=" * 60)
    print(f"Serialized {len(events)} events")
    print(f"Event 1 lane_id: {events[0]['lane_id']}")
    print(f"Event 2 lane_id: {events[1]['lane_id']}")

    # Test with centroid outside all lanes
    vehicle_no_lane = vehicle.copy()
    vehicle_no_lane["centroid"] = {"x": 300, "y": 300}  # Outside all lanes
    event_no_lane = serializer.serialize_event(vehicle_no_lane, "cam_north_approach", 18424, test_timestamp)

    print("\n" + "=" * 60)
    print("No Lane Match Test:")
    print("=" * 60)
    print(f"Lane ID for out-of-bounds point: {event_no_lane['lane_id']}")
    assert event_no_lane["lane_id"] is None, "Should return None for out-of-bounds point"
    print("✓ Correctly returns None for points outside all lanes")

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == "__main__":
    test_enricher()
