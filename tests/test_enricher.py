import pytest
from datetime import datetime, timezone
from src.analytics.enricher import LaneEnricher, EventSerializer

FAKE_LANES_CONFIG = {
    "lanes": [
        {
            "id": "lane_1",
            "polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
        },
        {
            "id": "lane_2",
            "polygon": [[10.0, 0.0], [20.0, 0.0], [20.0, 10.0], [10.0, 10.0]]
        }
    ]
}

@pytest.fixture
def enricher():
    return LaneEnricher(FAKE_LANES_CONFIG)

def test_map_to_lane_inside(enricher):
    assert enricher.map_to_lane({"x": 5.0, "y": 5.0}) == "lane_1"
    assert enricher.map_to_lane({"x": 15.0, "y": 5.0}) == "lane_2"

def test_map_to_lane_outside(enricher):
    assert enricher.map_to_lane({"x": 50.0, "y": 50.0}) is None

@pytest.fixture
def serializer(enricher):
    return EventSerializer(enricher)

def test_serialize_event_schema_and_mappings(serializer):
    fake_vehicle = {
        "id": 203,
        "vehicle_id": "veh_203",
        "class": "car",
        "confidence": 0.93,
        "bbox": [412, 178, 494, 224],
        "bbox_xywh": {"x": 412, "y": 178, "w": 82, "h": 46},
        "centroid": {"x": 5.0, "y": 5.0},
        "frame_id": 18422,
        "speed_kmh": 34.2
    }

    event = serializer.serialize_event(
        vehicle=fake_vehicle,
        camera_id="cam_north",
        frame_id=18422,
        timestamp=1681640123.456
    )

    expected_keys = {
        "camera_id",
        "timestamp",
        "frame_id",
        "vehicle_id",
        "class",
        "confidence",
        "bbox",
        "centroid",
        "lane_id",
        "speed_estimate"
    }

    assert set(event.keys()) == expected_keys
    assert event["bbox"] == {"x": 412, "y": 178, "w": 82, "h": 46}
    assert event["speed_estimate"] == 34.2
    assert event["lane_id"] == "lane_1"
    assert event["vehicle_id"] == "veh_203"
    assert event["class"] == "car"

def test_serialize_batch(serializer):
    fake_vehicles = [
        {"id": 1, "centroid": {"x": 5.0, "y": 5.0}},
        {"id": 2, "centroid": {"x": 15.0, "y": 5.0}}
    ]
    
    events = serializer.serialize_batch(fake_vehicles, camera_id="cam_1")
    assert len(events) == 2
    assert events[0]["lane_id"] == "lane_1"
    assert events[1]["lane_id"] == "lane_2"

def test_serialize_event_bbox_fallback(serializer):
    fake_vehicle = {
        "id": 7,
        "class": "car",
        "confidence": 0.5,
        "bbox": [0, 0, 10, 10],
    }

    event = serializer.serialize_event(fake_vehicle, camera_id="cam_1")

    assert event["bbox"] == {"x": 0, "y": 0, "w": 10, "h": 10}
    assert event["centroid"] == {"x": 5.0, "y": 5.0}
    assert event["lane_id"] == "lane_1"

    inverted_vehicle = {**fake_vehicle, "bbox": [10, 10, 0, 0]}
    inverted_event = serializer.serialize_event(inverted_vehicle, camera_id="cam_1")
    assert inverted_event["bbox"] == {"x": 0, "y": 0, "w": 10, "h": 10}
    assert inverted_event["centroid"] == {"x": 5.0, "y": 5.0}

def test_timestamp_formatting(serializer):
    fake_vehicle = {"id": 1, "centroid": {"x": 5.0, "y": 5.0}}
    
    e1 = serializer.serialize_event(fake_vehicle, "cam_1", timestamp=1681640123.0)
    assert str(e1["timestamp"]).endswith("Z")
    
    e2 = serializer.serialize_event(fake_vehicle, "cam_1", timestamp=datetime.now(timezone.utc))
    assert str(e2["timestamp"]).endswith("Z")
    
    e3 = serializer.serialize_event(fake_vehicle, "cam_1", timestamp="2026-04-16T10:15:23.456")
    assert str(e3["timestamp"]).endswith("Z")
