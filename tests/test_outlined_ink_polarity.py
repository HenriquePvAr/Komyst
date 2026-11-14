"""Dark lettering with a thick white outline must not be read as white ink.

On a light page the outline can outnumber the ink pixels; taking the majority colour as the ink inverted
the lettering and rendered it white on white (invisible). Synthetic pixels only.
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from komyst.ocr import ocr_balloon as ob
from komyst.ocr.ocr_balloon import OCRLine, TextGroup


def _font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _page(background, ink, outline, stroke=6):
    image = Image.new("RGB", (460, 200), background)
    draw = ImageDraw.Draw(image)
    draw.text((30, 40), "ABCDEFGH", font=_font(64), fill=ink, stroke_width=stroke, stroke_fill=outline)
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _group():
    polygon = np.array([[24, 34], [440, 34], [440, 130], [24, 130]], dtype=np.int32)
    line = OCRLine(text="ABCDEFGH", confidence=0.95, polygon=polygon, box=(24, 34, 416, 96),
                   raw_text="ABCDEFGH", engine="rapidocr", page=1)
    return TextGroup(group_id="T001", lines=[line], text="ABCDEFGH", classification="narration",
                     inside_balloon_like_region=False, source_engine="rapidocr")


BOX = (24, 34, 416, 96)


def test_dark_ink_with_a_thick_white_outline_on_a_light_page_stays_dark():
    image = _page(background=(226, 222, 218), ink=(18, 18, 18), outline=(255, 255, 255))
    profile = ob.extract_original_lettering_profile(image, _group(), BOX, fill_ink=True)
    assert profile["color_family"] == "black"
    assert max(profile["dominant_bgr"]) <= 80
    assert profile["stroke_present"] and min(profile["stroke_color"]) >= 185


def test_white_ink_with_a_dark_outline_stays_white():
    image = _page(background=(226, 222, 218), ink=(255, 255, 255), outline=(18, 18, 18))
    profile = ob.extract_original_lettering_profile(image, _group(), BOX, fill_ink=True)
    assert profile["color_family"] == "white"
    assert min(profile["dominant_bgr"]) >= 185


def test_the_cleanup_reading_keeps_the_majority_colour():
    """The cleanup is calibrated on the majority reading; only typography asks for the fill."""
    image = _page(background=(226, 222, 218), ink=(18, 18, 18), outline=(255, 255, 255))
    profile = ob.extract_original_lettering_profile(image, _group(), BOX)
    assert profile["color_family"] == "white"



def test_dark_ink_in_a_white_outline_over_textured_art_is_dark():
    """On textured art both k-means clusters come out white; the enclosed dark core is the ink."""
    rng = np.random.default_rng(3)
    y, x = np.arange(200)[:, None], np.arange(460)[None, :]
    gray = np.clip(174 + np.sin(x / 7.0 + y / 40.0) * 35 + rng.normal(0, 10, (200, 460)), 0, 255)
    art = np.clip(np.stack([gray * 1.05, gray * 0.85, gray * 0.6], axis=2), 0, 255).astype(np.uint8)
    image = Image.fromarray(art)
    draw = ImageDraw.Draw(image)
    draw.text((30, 50), "ABCDEFGH IJK", font=_font(30), fill=(12, 12, 12), stroke_width=6,
              stroke_fill=(250, 250, 250))
    bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    profile = ob.extract_original_lettering_profile(bgr, _group(), BOX, fill_ink=True)
    assert profile["color_family"] == "black"
    assert max(profile["dominant_bgr"]) <= 80
