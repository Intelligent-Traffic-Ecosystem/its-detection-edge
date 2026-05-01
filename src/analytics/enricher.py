from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone

class LaneEnricher:
    def __init__(self, lanes_config: Dict[str, Any]):
        """
        lanes_config is a list of dicts like:
        [{"id": "lane_1", "polygon": [[x1, y1], [x2, y2], ...]}, ...]
        """
        self.lanes = lanes_config.get("lanes", [])

    def map_to_lane(self, centroid: Dict[str, float]) -> Optional[str]:
        """
        Maps a centroid point to a lane ID.
        """
        x = centroid.get("x")
        y = centroid.get("y")
        
        if x is None or y is None:
            return None
            
        for lane in self.lanes:
            if self._is_point_in_polygon(x, y, lane.get("polygon", [])):
                return lane.get("id")
        
        return None

    def _is_point_in_polygon(self, x: float, y: float, polygon: List[List[float]]) -> bool:
        """Ray Casting algorithm for point-in-polygon test."""
        if not polygon:
            return False
            
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside


class EventSerializer:
    def __init__(self, lane_enricher: LaneEnricher):
        self.lane_enricher = lane_enricher

    def _format_timestamp(self, ts: Union[float, int, str, datetime, None]) -> str:
        """Helper to ensure timestamp is UTC ISO 8601 ending in Z."""
        if ts is None:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        elif isinstance(ts, (float, int)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        elif isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.isoformat().replace("+00:00", "Z")
        elif isinstance(ts, str):
            if "+00:00" in ts:
                return ts.replace("+00:00", "Z")
            if not ts.endswith("Z"):
                return ts + "Z"
            return ts
        return str(ts)

    def _get_centroid(self, vehicle: Dict[str, Any]) -> Dict[str, float]:
        """Extract or calculate the centroid."""
        if "centroid" in vehicle and isinstance(vehicle["centroid"], dict):
            return vehicle["centroid"]
        
        # Calculate from bbox if available
        bbox = vehicle.get("bbox")
        if bbox and len(bbox) >= 4:
            x1, y1, x2, y2 = bbox[:4]
            return {"x": round((x1 + x2) / 2, 2), "y": round((y1 + y2) / 2, 2)}
            
        return {"x": 0.0, "y": 0.0}

    def serialize_event(self, vehicle: Dict[str, Any], camera_id: str, frame_id: Optional[int] = None, timestamp: Union[float, int, str, datetime, None] = None) -> Dict[str, Any]:
        """Convert a raw detection dict into the strict event schema."""
        centroid = self._get_centroid(vehicle)
        lane_id = self.lane_enricher.map_to_lane(centroid)
        
        return {
            "camera_id": camera_id,
            "timestamp": self._format_timestamp(timestamp),
            "frame_id": frame_id if frame_id is not None else vehicle.get("frame_id"),
            "vehicle_id": vehicle.get("vehicle_id") or f"veh_{vehicle.get('id', 'unknown')}",
            "class": vehicle.get("class", vehicle.get("label", "unknown")),
            "confidence": vehicle.get("confidence", 0.0),
            "bbox": vehicle.get("bbox_xywh", {}),
            "centroid": centroid,
            "lane_id": lane_id,
            "speed_estimate": vehicle.get("speed_kmh", vehicle.get("speed", 0.0))
        }

    def serialize_batch(self, vehicles: List[Dict[str, Any]], camera_id: str, frame_id: Optional[int] = None, timestamp: Union[float, int, str, datetime, None] = None) -> List[Dict[str, Any]]:
        """Serialize a list of raw detections."""
        return [self.serialize_event(v, camera_id, frame_id, timestamp) for v in vehicles]
