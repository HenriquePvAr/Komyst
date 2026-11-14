"""Page-revision re-render: the page handed to the renderer is already clean, so the
typography must read its style from the original page and the translation must be
drawn on the clean background instead of falling back to a caption plate."""
import test_support._test_bootstrap as _test_bootstrap  # noqa: F401

import unittest

import cv2
import numpy as np

import komyst.ocr.ocr_balloon as ob
from komyst.ocr.ocr_engine import OCRLine

BOX = (60, 80, 180, 70)


def _group():
    x, y, w, h = BOX
    line = OCRLine(text="HELLO THERE FRIEND", confidence=0.9,
                   polygon=np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]),
                   box=BOX, raw_text="HELLO THERE FRIEND", engine="t", page=1)
    group = ob.TextGroup(group_id="BALAO_1", lines=[line], text="HELLO THERE FRIEND")
    group.cleanup_lines = [line]
    group.classification = "speech"
    group.translation = "OLA AMIGO"
    group.translation_valid = True
    group.background_type = "speech_balloon"
    return group


def _pages():
    clean = np.full((260, 300, 3), (205, 190, 175), np.uint8)  # tinted balloon, no text
    cv2.ellipse(clean, (150, 115), (120, 60), 0, 0, 360, (250, 250, 250), -1)
    source = clean.copy()
    for i in range(3):
        cv2.putText(source, "HELLO", (80, 100 + i * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return clean, source


def _plate_pixels(page, clean):
    """Pixels that changed on the page outside the glyph area: a plate paints a block."""
    diff = np.any(page != clean, axis=2)
    return int(diff.sum())


class PreCleanedRenderTests(unittest.TestCase):
    def test_style_is_read_from_the_source_page_and_no_plate_is_drawn(self):
        clean, source = _pages()
        group = _group()
        group.pre_cleaned = True
        full, _ = ob.render_analyzed_image(clean, [], [], [group], page_index=1,
                                           style_source_bgr=source)
        self.assertTrue(group.redrawn)
        self.assertNotIn("translation_label", str(getattr(group, "render_mode", "")))
        self.assertNotIn("translation_label", str(group.render_disposition_reason))
        profile = group.typography_profile
        fill = profile.get("fill_color")
        self.assertIsNotNone(fill)
        self.assertLess(max(fill), 90, f"ink should be dark, got {fill}")
        # a plate would repaint the whole box border; glyphs touch a small share of it
        x, y, w, h = BOX
        changed = np.any(full[y:y + h, x:x + w] != clean[y:y + h, x:x + w], axis=2).mean()
        self.assertLess(changed, 0.45)

    def test_without_the_flag_nothing_changes(self):
        clean, _source = _pages()
        group = _group()
        ob.render_analyzed_image(clean, [], [], [group], page_index=1)
        self.assertFalse(getattr(group, "pre_cleaned", False))


if __name__ == "__main__":
    unittest.main()
