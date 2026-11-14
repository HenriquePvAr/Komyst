"""Speech-balloon detector (RT-DETR-v2 r50vd, ogkalu/comic-text-and-bubble-detector, Apache-2.0).

Opt-in (``BUBBLE_DETECTOR_ENABLED``); the weights are not bundled, they live at
``BUBBLE_DETECTOR_MODEL``. Nothing is imported or loaded while it is off. The model takes a
640x640 RGB tile and returns boxes in tile pixels, so a tall page is run as overlapping
square tiles and the boxes merged. Classes: 0 bubble, 1 text_bubble, 2 text_free.
"""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import cv2
import numpy as np

import komyst.config.settings as config

_SIZE = 640
_LOCK = threading.Lock()
_SESSION = None  # False once loading failed, so it is not retried per region
_PAGES = {}  # tiny cache: page fingerprint -> boxes (regions of one page ask repeatedly)


def _session():
    global _SESSION
    with _LOCK:
        if _SESSION is None:
            _SESSION = False
            path = Path(config.BUBBLE_DETECTOR_MODEL)
            if path.is_file():
                import onnxruntime as ort

                options = ort.SessionOptions()
                options.enable_mem_pattern = False
                options.log_severity_level = 3
                try:
                    from komyst.core.gpu import DIRECTML_LOCK

                    with DIRECTML_LOCK:
                        _SESSION = ort.InferenceSession(
                            str(path), sess_options=options,
                            providers=["DmlExecutionProvider", "CPUExecutionProvider"])
                except Exception:
                    try:
                        _SESSION = ort.InferenceSession(
                            str(path), sess_options=options, providers=["CPUExecutionProvider"])
                    except Exception:
                        _SESSION = False
        return _SESSION


def _run(session, tile_bgr):
    side_h, side_w = tile_bgr.shape[:2]
    rgb = cv2.cvtColor(cv2.resize(tile_bgr, (_SIZE, _SIZE), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    x = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0)
    feeds = {"images": x, "orig_target_sizes": np.array([[side_h, side_w]], dtype=np.int64)}
    try:
        from komyst.core.gpu import DIRECTML_LOCK

        with DIRECTML_LOCK:
            labels, boxes, scores = session.run(None, feeds)
    except Exception:
        return []
    return [(*(float(v) for v in b), float(s)) for l, b, s in zip(labels[0], boxes[0], scores[0])
            if int(l) == 0 and s >= config.BUBBLE_DETECTOR_MIN_SCORE]


def _merge(boxes):
    """Drop a box whose area is mostly inside a higher-scoring one (tile overlaps)."""
    kept = []
    for b in sorted(boxes, key=lambda v: -v[4]):
        area = max(1.0, (b[2] - b[0]) * (b[3] - b[1]))
        for k in kept:
            iw = min(b[2], k[2]) - max(b[0], k[0])
            ih = min(b[3], k[3]) - max(b[1], k[1])
            if iw > 0 and ih > 0 and iw * ih / area > 0.7:
                break
        else:
            kept.append(b)
    return kept


def detect_bubbles(img_bgr):
    """[(x1, y1, x2, y2, score)] balloons on the page, in page pixels; [] when unavailable."""
    if not config.BUBBLE_DETECTOR_ENABLED:
        return []
    key = (img_bgr.shape, hashlib.sha1(np.ascontiguousarray(img_bgr[::7, ::7]).tobytes()).hexdigest())
    if key in _PAGES:
        return _PAGES[key]
    session = _session()
    if not session:
        return []
    height, width = img_bgr.shape[:2]
    side = max(width, min(height, _SIZE))
    step = max(1, int(side * 0.6))
    found = []
    for top in sorted({min(t, max(0, height - side)) for t in range(0, max(1, height - side + step), step)}):
        tile = img_bgr[top:top + side]
        for x1, y1, x2, y2, score in _run(session, tile):
            found.append((x1, y1 + top, x2, y2 + top, score))
    result = _merge(found)
    if len(_PAGES) >= 4:
        _PAGES.pop(next(iter(_PAGES)))
    _PAGES[key] = result
    return result


def balloon_interior(img_bgr, region_box):
    """Boolean page-sized mask of the detected balloon holding ``region_box`` (x, y, w, h), or None.

    The balloon box limits the search; inside it the interior is the connected area of the balloon's
    fill colour (median of the box, so coloured balloons work) around the text, holes closed. A fill
    that breaks up (under 35 % of the box) falls back to the ellipse inscribed in the box.
    """
    x, y, w, h = (int(v) for v in region_box)
    holders = [b for b in detect_bubbles(img_bgr)
               if b[0] - 0.05 * w <= x and b[1] - 0.05 * h <= y
               and x + w <= b[2] + 0.05 * w and y + h <= b[3] + 0.05 * h]
    if not holders:
        return None
    bx1, by1, bx2, by2, _ = min(holders, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    bx1, by1 = max(0, int(bx1)), max(0, int(by1))
    bx2, by2 = min(img_bgr.shape[1], int(np.ceil(bx2))), min(img_bgr.shape[0], int(np.ceil(by2)))
    bw, bh = bx2 - bx1, by2 - by1
    if bw < 8 or bh < 8:
        return None
    ellipse = np.zeros((bh, bw), np.uint8)
    cv2.ellipse(ellipse, (bw // 2, bh // 2), (max(1, bw // 2 - 1), max(1, bh // 2 - 1)), 0, 0, 360, 1, -1)
    lab = cv2.cvtColor(img_bgr[by1:by2, bx1:bx2], cv2.COLOR_BGR2LAB).astype(np.float32)
    fill = np.median(lab.reshape(-1, 3), axis=0)
    near = (np.linalg.norm(lab - fill, axis=2) < 22).astype(np.uint8)
    near = cv2.morphologyEx(near, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))  # text ink / thin gaps
    _, labels = cv2.connectedComponents(near, connectivity=4)
    ids = np.unique(labels[max(0, y - by1):max(1, y - by1 + h), max(0, x - bx1):max(1, x - bx1 + w)])
    ids = [i for i in ids if i]
    local = np.isin(labels, ids).astype(np.uint8) if ids else ellipse.copy()
    local = cv2.morphologyEx(local, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    contours, _ = cv2.findContours(local, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(local)
    cv2.drawContours(filled, contours, -1, 1, -1)  # fills the text's holes
    if filled.sum() < 0.35 * bw * bh:
        filled = ellipse
    page = np.zeros(img_bgr.shape[:2], dtype=bool)
    page[by1:by2, bx1:bx2] = filled > 0
    return page
