# Serializing & Enrichment Layer Documentation

## Overview
The `src/analytics/enricher.py` module provides the middle layer for serializing raw vehicle detections from the YOLO detector and enriching them with lane information.

## Components

### 1. LaneEnricher
Maps vehicle positions to lane IDs using point-in-polygon detection.

**Initialization:**
```python
from src.analytics.enricher import LaneEnricher
import json

# Load lane configuration
with open("config/lanes.json", "r") as f:
    lanes_config = json.load(f)

# Initialize enricher
enricher = LaneEnricher(lanes_config)
```

**Lane Configuration Format (config/lanes.json):**
```json
{
  "camera_id": "cam_01",
  "lanes": [
    {
      "id": "lane_1",
      "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]],
      "direction": "inbound"
    },
    {
      "id": "lane_2",
      "polygon": [[100, 0], [200, 0], [200, 100], [100, 100]],
      "direction": "outbound"
    }
  ]
}
```

**Usage:**
```python
# Map a vehicle centroid to a lane
centroid = {"x": 50, "y": 50}
lane_id = enricher.map_to_lane(centroid)
# Returns: "lane_1" (or None if outside all lanes)
```

### 2. EventSerializer
Converts raw vehicle detections into the strict JSON event schema.

**Initialization:**
```python
from src.analytics.enricher import EventSerializer

# Create serializer with enricher
serializer = EventSerializer(enricher)
```

**Input Vehicle Format** (from YOLO detector):
```python
vehicle = {
    "vehicle_id": "veh_203",
    "class": "car",                          # Vehicle type
    "confidence": 0.93,                      # Detection confidence [0, 1]
    "bbox": {"x": 412, "y": 178, "w": 82, "h": 46},  # Bounding box
    "centroid": {"x": 453, "y": 201},       # Center point
    "speed": 34.2                            # Speed in km/h
}
```

**Serializing Single Event:**
```python
from datetime import datetime, timezone

# Option 1: With explicit timestamp
timestamp = datetime(2026, 4, 16, 10, 15, 23, 456000, tzinfo=timezone.utc)
event = serializer.serialize_event(
    vehicle=vehicle,
    camera_id="cam_north_approach",
    frame_id=18422,
    timestamp=timestamp
)

# Option 2: With Unix timestamp
timestamp_unix = 1234567890.456
event = serializer.serialize_event(
    vehicle=vehicle,
    camera_id="cam_north_approach",
    frame_id=18422,
    timestamp=timestamp_unix
)

# Option 3: Use current UTC time
event = serializer.serialize_event(
    vehicle=vehicle,
    camera_id="cam_north_approach",
    frame_id=18422
)
```

**Output Event Format:**
```python
{
    "camera_id": "cam_north_approach",
    "timestamp": "2026-04-16T10:15:23.456Z",    # UTC ISO 8601 with Z
    "frame_id": 18422,
    "vehicle_id": "veh_203",
    "class": "car",
    "confidence": 0.93,
    "bbox": {"x": 412, "y": 178, "w": 82, "h": 46},
    "centroid": {"x": 453, "y": 201},
    "lane_id": 1,                              # None if outside all lanes
    "speed_estimate": 34.2
}
```

**Serializing Batch (Multiple Vehicles):**
```python
vehicles = [vehicle1, vehicle2, vehicle3, ...]

events = serializer.serialize_batch(
    vehicles=vehicles,
    camera_id="cam_north_approach",
    frame_id=18422,
    timestamp=None  # Uses current UTC time
)
# Returns: List of serialized event dicts
```

## Integration with main.py

```python
import json
from src.analytics.enricher import LaneEnricher, EventSerializer

# Load lane config
with open("config/lanes.json", "r") as f:
    lanes_config = json.load(f)

# Initialize components
enricher = LaneEnricher(lanes_config)
serializer = EventSerializer(enricher)

# In your main loop, after detector.detect_and_track():
while True:
    frame = stream.get_frame()
    frame_id = get_frame_id()  # Your frame counter
    
    # Get raw detections from YOLO
    vehicles = detector.detect_and_track(frame)
    
    # Serialize to events
    events = serializer.serialize_batch(
        vehicles=vehicles,
        camera_id="cam_01",
        frame_id=frame_id
        # timestamp defaults to current UTC time
    )
    
    # Send to Kafka or buffer
    for event in events:
        producer.send_event(event)
```

## Type Hints

All functions include full type hints for IDE support:

```python
from typing import Dict, List, Any, Optional

def serialize_event(
    vehicle: Dict[str, Any],
    camera_id: str,
    frame_id: int,
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Returns serialized event dictionary."""
```

## Error Handling

- **Missing centroid**: Returns `lane_id = None`
- **Invalid centroid format**: Handles gracefully, returns `None`
- **Out-of-bounds point**: Returns `lane_id = None`
- **Missing vehicle fields**: Returned as `None` in event dict (validate before sending)
- **Timestamp edge cases**: Converts Unix timestamps, handles timezones automatically

## Testing

Run the comprehensive test suite:
```bash
python tests/test_enricher.py
```

This verifies:
- Single event serialization
- Batch serialization
- Lane mapping (inside/outside)
- Timestamp formatting
- Edge cases

---

**Developer 2**: This layer is ready to receive vehicle detections from Developer 1 (detector) and is ready to send serialized events to Developer 3 (Kafka/buffering).
