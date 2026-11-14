"""Optional balloon detector: hermetic (no model file, the ONNX session is faked)."""
import numpy as np

import komyst.config.settings as config
import komyst.ocr.bubble_detector as bd
import komyst.ocr.ocr_balloon as ob
from komyst.ocr.ocr_engine import OCRLine


def _group(box):
    x, y, w, h = box
    poly = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], np.int32)
    line = OCRLine("HI", 0.97, poly, box, "HI", engine="synthetic", metadata={"ocr_line_id": "L1"})
    return ob.TextGroup(group_id="g", lines=[line], text="HI", classification="speech")


def _page():
    img = np.full((300, 300, 3), 255, np.uint8)
    img[60:240, 40:260] = (230, 200, 120)  # coloured balloon (no white interior at all)
    img[140:160, 130:170] = (40, 40, 40)   # text ink
    return img


class _FakeSession:
    def run(self, _outputs, feeds):
        assert feeds["images"].shape == (1, 3, 640, 640)
        return (np.array([[0, 2]]), np.array([[[40, 60, 260, 240], [1, 1, 5, 5]]], np.float32),
                np.array([[0.9, 0.9]], np.float32))


def _enable(monkeypatch):
    monkeypatch.setattr(config, "BUBBLE_DETECTOR_ENABLED", True)
    monkeypatch.setattr(bd, "_SESSION", _FakeSession())
    monkeypatch.setattr(bd, "_PAGES", {})


def test_disabled_never_touches_the_model(monkeypatch):
    monkeypatch.setattr(config, "BUBBLE_DETECTOR_ENABLED", False)
    monkeypatch.setattr(bd, "_SESSION", None)
    assert bd.detect_bubbles(_page()) == []
    assert bd.balloon_interior(_page(), (130, 140, 40, 20)) is None
    assert bd._SESSION is None  # nothing loaded
    assert ob._balloon_text_area(_group((130, 140, 40, 20)), (300, 300, 3), _page()) is None


def test_missing_model_degrades_to_no_detection(monkeypatch):
    monkeypatch.setattr(config, "BUBBLE_DETECTOR_ENABLED", True)
    monkeypatch.setattr(config, "BUBBLE_DETECTOR_MODEL", "does-not-exist.onnx")
    monkeypatch.setattr(bd, "_SESSION", None)
    assert bd.detect_bubbles(_page()) == []


def test_only_bubble_class_is_kept_and_text_inside_picks_it(monkeypatch):
    _enable(monkeypatch)
    boxes = bd.detect_bubbles(_page())
    assert len(boxes) == 1 and boxes[0][:4] == (40.0, 60.0, 260.0, 240.0)
    assert bd.balloon_interior(_page(), (10, 10, 20, 20)) is None  # outside every balloon


def test_text_area_follows_the_detected_coloured_balloon(monkeypatch):
    _enable(monkeypatch)
    group = _group((130, 140, 40, 20))
    area = ob._balloon_text_area(group, (300, 300, 3), _page())
    assert area is not None and area[150, 150]
    assert not area[150, 20] and not area[30, 150]            # outside the balloon
    ys, xs = np.nonzero(area)
    assert xs.min() >= 40 and xs.max() <= 260 and ys.min() >= 60 and ys.max() <= 240
    assert area.sum() > 0.5 * 220 * 180 * 0.6                 # most of the balloon, minus the margin


def test_without_detection_the_white_interior_path_is_unchanged(monkeypatch):
    _enable(monkeypatch)
    interior = np.zeros((300, 300), bool)
    interior[20:40, 20:40] = True
    group = _group((22, 22, 10, 10))
    group.light_enclosure_interior = interior
    with_detector = ob._balloon_text_area(group, (300, 300, 3), _page())  # box not inside the detected balloon
    monkeypatch.setattr(config, "BUBBLE_DETECTOR_ENABLED", False)
    assert np.array_equal(with_detector, ob._balloon_text_area(group, (300, 300, 3), _page()))
