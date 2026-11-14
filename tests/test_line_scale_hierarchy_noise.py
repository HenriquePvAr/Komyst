"""A size hierarchy is drawn only when the source really shows one.

Uniform lettering was drawn with lines of different sizes because the per-line
ink height read a short all-caps line (bars far denser than stems) as ~60 % of
its real height, because boxes of equal height still produced a ratio from
noisy ink, and because one unmeasurable line sent the whole group to box heights.
"""
import os
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import komyst.ocr.ocr_balloon as ob
from komyst.ocr.ocr_engine import OCRLine

FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def _group(font_file, specs, box_heights=None):
    """specs: [(text, font size)]; one line per row, tight boxes unless overridden."""
    path = FONTS / font_file
    if not path.exists():
        raise unittest.SkipTest(f"{font_file} not installed")
    image = Image.new("RGB", (700, 40 + 110 * len(specs)), "white")
    draw = ImageDraw.Draw(image)
    lines = []
    for index, (text, size) in enumerate(specs):
        font = ImageFont.truetype(str(path), size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        x, y = (700 - (right - left)) // 2, 30 + index * 110
        if text.strip():
            draw.text((x - left, y - top), text, font=font, fill="black")
        h = (box_heights[index] if box_heights else bottom - top) + 8
        box = (x - 4, y - 4, right - left + 8, h)
        bx, by, bw, bh = box
        polygon = np.array([[bx, by], [bx + bw, by], [bx + bw, by + bh], [bx, by + bh]], dtype=np.int32)
        lines.append(OCRLine(text=text or "X", confidence=0.99, polygon=polygon, box=box,
                             raw_text=text, engine="rapidocr", page=1))
    bgr = np.asarray(image)[:, :, ::-1].copy()
    return bgr, ob.TextGroup(group_id="BALAO_1", lines=lines, text=" ".join(t for t, _ in specs))


class LineScaleHierarchyNoiseTests(unittest.TestCase):
    def test_short_all_caps_line_keeps_its_height(self):
        bgr, group = _group("arial.ttf", [("LET'S", 40), ("SEE IF MY", 40), ("HEART STOPS", 40)])
        heights = [ob._line_ink_height(bgr, line.box) for line in group.lines]
        self.assertGreater(min(heights) / max(heights), 0.9, heights)
        self.assertIsNone(ob._source_line_scale_ratios(group, bgr))

    def test_equal_boxes_with_noisy_ink_are_not_a_hierarchy(self):
        # ink 40 vs 24 px but the OCR boxes are the same height: lines of one size
        bgr, group = _group("comicbd.ttf", [("GET YOUR", 40), ("HANDS OFF", 24)], box_heights=[44, 44])
        self.assertIsNone(ob._source_line_scale_ratios(group, bgr))

    def test_unmeasurable_line_does_not_fall_back_to_box_heights(self):
        bgr, group = _group("comicbd.ttf", [("SEEMS FINE", 30), ("", 30), ("NOW", 30)], box_heights=[30, 30, 60])
        self.assertIsNone(ob._source_line_scale_ratios(group, bgr))

    def test_real_title_plus_small_text_is_still_a_hierarchy(self):
        bgr, group = _group("comicbd.ttf", [("small intro", 26), ("BIG TITLE", 60)])
        ratios = ob._source_line_scale_ratios(group, bgr)
        self.assertIsNotNone(ratios)
        self.assertLess(ratios[0], 1.0)
        self.assertGreater(ratios[1], 1.0)


if __name__ == "__main__":
    unittest.main()
