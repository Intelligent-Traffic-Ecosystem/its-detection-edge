from typing import Dict, List, Any, Optional

class LaneEnricher:
    def __init__(self, lanes_config: Dict[str, Any]):
        """
        lanes_config is a list of dicts like:
        [{"id": "lane_1", "polygon": [[x1, y1], [x2, y2], ...]}, ...]
        """
        self.lanes = lanes_config.get("lanes", [])

    def map_to_lane(self, bbox: List[float]) -> Optional[str]:
        """
        Maps a bounding box (bottom-center point) to a lane ID.
        bbox format: [x1, y1, x2, y2]
        """
        # We use the bottom center of the bounding box as the reference point
        x = (bbox[0] + bbox[2]) / 2
        y = bbox[3]
        
        for lane in self.lanes:
            if self._is_point_in_polygon(x, y, lane.get("polygon", [])):
                return lane.get("id")
        
        return "unknown"

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
