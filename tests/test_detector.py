import numpy as np

from src.ml.detector import TrafficDetector


class FakeTensor:
    def __init__(self, values):
        self.values = np.array(values)

    def cpu(self):
        return self

    def numpy(self):
        return self.values


class FakeBoxes:
    def __init__(self):
        self.xyxy = FakeTensor([[10, 20, 50, 80], [100, 120, 160, 220]])
        self.id = FakeTensor([7, 8])
        self.cls = FakeTensor([2, 0])
        self.conf = FakeTensor([0.91, 0.44])


class FakeResult:
    def __init__(self):
        self.boxes = FakeBoxes()


class FakeModel:
    names = {0: "person", 2: "car"}

    def __init__(self):
        self.calls = 0

    def track(self, **kwargs):
        self.calls += 1
        return [FakeResult()]


def test_detector_returns_per_object_confidence_and_shape():
    model = FakeModel()
    detector = TrafficDetector(model=model, allowed_classes={"car", "person"})

    objects = detector.detect_and_track(np.zeros((240, 320, 3), dtype=np.uint8))

    assert len(objects) == 2
    assert objects[0]["vehicle_id"] == "veh_7"
    assert objects[0]["class"] == "car"
    assert objects[0]["confidence"] == 0.91
    assert objects[0]["bbox_xywh"] == {"x": 10.0, "y": 20.0, "w": 40.0, "h": 60.0}
    assert objects[0]["centroid"] == {"x": 30.0, "y": 50.0}
    assert objects[1]["confidence"] == 0.44


def test_detector_filters_unwanted_classes_and_skips_frames():
    model = FakeModel()
    detector = TrafficDetector(model=model, frame_skip=1, allowed_classes={"car"})

    first = detector.detect_and_track(np.zeros((240, 320, 3), dtype=np.uint8))
    second = detector.detect_and_track(np.zeros((240, 320, 3), dtype=np.uint8))

    assert len(first) == 1
    assert first[0]["class"] == "car"
    assert second == []
    assert model.calls == 1
