import pytest
from src.analytics.enricher import LaneEnricher

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
