"""Thin low-contrast lettering on a light, uniform box must leave no ghost after Clean.

The box ring is measured (PROVEN_UNIFORM); the second text line and the box border inside
the flatness ring used to make a flat fill read as a "flat patch on textured art", so the
first line was rejected and survived (LOCAL_HARD) or the page lost its Clean certificate.
"""
import cv2
import numpy as np

import komyst.ocr.ocr_balloon as ob
from komyst.ocr.ocr_engine import OCRLine

BG = (247, 238, 214)
INK = (70, 40, 35)
LINES = ("EVEN BACK WHEN", "THEY BROKE UP--")
# measured on this page: unfixed -> max residue 226 grey levels, 4128 pixels over 16 (the first
# line survives whole); fixed -> max 17, 5 pixels over 8 (isolated JPEG ringing). The box's own
# noise far from the text is <= 4.
GHOST_LIMIT = 20
GHOST_PIXELS_OVER_8 = 20


def _page(jpeg_quality=70, ink=INK, scale=0.7):
    h, w = 200, 420
    img = np.full((h, w, 3), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (w - 20, h - 20), BG, -1)
    cv2.rectangle(img, (20, 20), (w - 20, h - 20), (120, 100, 90), 2)
    big = np.zeros((h * 4, w * 4), np.uint8)
    for i, text in enumerate(LINES):
        cv2.putText(big, text, (280, (85 + i * 40) * 4), cv2.FONT_HERSHEY_DUPLEX, scale * 4, 255, 5, cv2.LINE_AA)
    alpha = cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    img = np.clip(img * (1 - alpha[..., None]) + np.array(ink, np.float32) * alpha[..., None], 0, 255).astype(np.uint8)
    img = cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])[1], 1)
    return img, alpha


def _lines(alpha):
    ys, xs = np.where(alpha > 0.05)
    out = []
    for (lo, hi), text in zip(((60, 100), (100, 140)), LINES):
        m = (ys >= lo) & (ys < hi)
        x0, x1, y0, y1 = xs[m].min(), xs[m].max() + 1, ys[m].min(), ys[m].max() + 1
        poly = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.int32)
        out.append(OCRLine(text, 0.97, poly, (int(x0), int(y0), int(x1 - x0), int(y1 - y0)), text,
                           engine="synthetic", metadata={"ocr_line_id": f"l{lo}"}))
    return out


def _clean(**kw):
    img, alpha = _page(**kw)
    lines = _lines(alpha)
    cands, groups = ob.analyze_image_array(img, lines, page_index=1)
    ob.apply_group_translations(ob.get_translatable_groups(groups), ["Texto de exemplo"] * len(groups))
    cap = {}
    ob._render_analyzed_image(img.copy(), lines, cands, groups, page_index=1, stage_timings={},
                              capture=cap, typeset=True)
    return img, cap["cleaned_bgr"], groups


def test_no_ghost_left_inside_light_box():
    img, cleaned, groups = _clean()
    inside = np.zeros(img.shape[:2], bool)
    inside[30:170, 30:390] = True
    residue = np.abs(cleaned.astype(int) - np.array(BG)).max(2)[inside]
    assert residue.max() < GHOST_LIMIT, residue.max()
    assert int((residue > 8).sum()) <= GHOST_PIXELS_OVER_8, int((residue > 8).sum())
    assert all(g.clean_disposition == "LOCAL_SAFE" for g in groups), [g.clean_disposition for g in groups]


def test_box_border_and_outside_art_unchanged():
    img, cleaned, _ = _clean()
    keep = np.ones(img.shape[:2], bool)
    keep[30:170, 30:390] = False  # everything but the box interior: border, outside, page margin
    assert np.array_equal(cleaned[keep], img[keep])


def test_low_contrast_ink_leaves_no_ghost():
    # ink only ~95 grey levels off the box: it used to sit under the foreground threshold
    # (the dense line drags the box median onto the ink) and the whole line survived.
    img, cleaned, groups = _clean(ink=(160, 130, 110), scale=1.2)
    inside = np.zeros(img.shape[:2], bool)
    inside[30:170, 30:390] = True
    residue = np.abs(cleaned.astype(int) - np.array(BG)).max(2)[inside]
    assert residue.max() < GHOST_LIMIT, residue.max()
    assert all(g.clean_disposition == "LOCAL_SAFE" for g in groups)
