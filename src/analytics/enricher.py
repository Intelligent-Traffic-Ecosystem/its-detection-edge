from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


class LaneEnricher:
    """Maps vehicle positions to lane IDs using point-in-polygon test."""

    def __init__(self, lanes_config: Dict[str, Any]):
        """
        Initialize lane enricher with lane polygon data.

        Args:
            lanes_config: Dict with structure:
                {
                    "camera_id": "cam_01",
                    "lanes": [
                        {"id": "lane_1", "polygon": [[x1, y1], [x2, y2], ...], "direction": "..."},
                        ...
                    ]
                }
        """
        self.lanes = lanes_config.get("lanes", [])

    def map_to_lane(self, centroid: Dict[str, float]) -> Optional[int | str]:
        """
        Maps a vehicle's centroid point to a lane ID using point-in-polygon test.

        Args:
            centroid: Dict with {"x": float, "y": float}

        Returns:
            Lane ID if point is inside a polygon, None otherwise.
        """
        x = centroid.get("x")
        y = centroid.get("y")

        if x is None or y is None:
            return None

        for lane in self.lanes:
            polygon = lane.get("polygon", [])
            if self._is_point_in_polygon(x, y, polygon):
                return lane.get("id")

        return None

    @staticmethod
    def _is_point_in_polygon(x: float, y: float, polygon: List[List[float]]) -> bool:
        """
        Ray Casting algorithm for point-in-polygon test.

        Args:
            x: X coordinate of point
            y: Y coordinate of point
            polygon: List of [x, y] coordinates forming a closed polygon

        Returns:
            True if point is inside polygon, False otherwise.
        """
        n = len(polygon)
        if n < 3:
            return False

        inside = False
        p1x, p1y = polygon[0]

        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                            if p1x == p2x or x <= xinters:
                                inside = not inside
                        elif p1x == p2x:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside


class EventSerializer:
    """Serializes raw vehicle detections into strict JSON event schema."""

    def __init__(self, enricher: LaneEnricher):
        """
        Initialize event serializer with a lane enricher.

        Args:
            enricher: LaneEnricher instance for mapping vehicles to lanes.
        """
        self.enricher = enricher

    def serialize_event(
        self,
        vehicle: Dict[str, Any],
        camera_id: str,
        frame_id: int,
        timestamp: Optional[datetime | float] = None,
    ) -> Dict[str, Any]:
        """
        Convert raw vehicle detection to strict JSON event schema.

        Args:
            vehicle: Raw vehicle dict from detector with keys:
                - vehicle_id: str
                - class: str (vehicle type, e.g., "car")
                - confidence: float [0, 1]
                - bbox: {"x": int, "y": int, "w": int, "h": int}
                - centroid: {"x": float, "y": float}
                - speed: float (speed estimate in km/h)
            camera_id: Camera identifier
            frame_id: Frame number
            timestamp: datetime object (UTC). If None, uses current UTC time.

        Returns:
            Dict with strict event schema:
            {
                "camera_id": str,
                "timestamp": str (ISO 8601 UTC with Z suffix),
                "frame_id": int,
                "vehicle_id": str,
                "class": str,
                "confidence": float,
                "bbox": {"x": int, "y": int, "w": int, "h": int},
                "centroid": {"x": float, "y": float},
                "lane_id": Optional[int | str],
                "speed_estimate": float
            }
        """
        # Use provided timestamp or current UTC time
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif isinstance(timestamp, float):
            # If timestamp is Unix timestamp, convert to datetime
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif not isinstance(timestamp, datetime):
            # If it's a string, try to parse it
            timestamp = datetime.now(timezone.utc)

        # Ensure timestamp is in UTC
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # Convert to ISO 8601 format with Z suffix
        iso_timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        # Get centroid from vehicle
        centroid = vehicle.get("centroid", {})

        # Map to lane using enricher
        lane_id = self.enricher.map_to_lane(centroid)

        # Build event dictionary
        event = {
            "camera_id": camera_id,
            "timestamp": iso_timestamp,
            "frame_id": frame_id,
            "vehicle_id": vehicle.get("vehicle_id"),
            "class": vehicle.get("class"),
            "confidence": vehicle.get("confidence"),
            "bbox": vehicle.get("bbox", {}),
            "centroid": centroid,
            "lane_id": lane_id,
            "speed_estimate": vehicle.get("speed"),
        }

        return event

    def serialize_batch(
        self,
        vehicles: List[Dict[str, Any]],
        camera_id: str,
        frame_id: int,
        timestamp: Optional[datetime | float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Serialize a batch of vehicles from a single frame.

        Args:
            vehicles: List of raw vehicle dicts
            camera_id: Camera identifier
            frame_id: Frame number
            timestamp: datetime object (UTC). If None, uses current UTC time.

        Returns:
            List of serialized event dicts.
        """
        events = []
        for vehicle in vehicles:
            event = self.serialize_event(vehicle, camera_id, frame_id, timestamp)
            events.append(event)
        return events
