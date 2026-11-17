"""The learned texture fill reconstructs over the lettering's halo, not just its glyphs."""
import test_support._test_bootstrap as _test_bootstrap  # noqa: F401

import types

import cv2
import numpy as np

import komyst.ocr.ocr_balloon as ob


def _stripes():
    truth = np.zeros((120, 220, 3), np.uint8)
    truth[:] = 150
    truth[:, ::12] = 60
    truth[:, 1::12] = 60
    return truth


def _text_on(truth, halo):
    image = truth.copy()
    glyph = np.zeros(truth.shape[:2], np.uint8)
    cv2.putText(glyph, "BOOM", (30, 80), cv2.FONT_HERSHEY_DUPLEX, 2.0, 255, 4, cv2.LINE_8)
    if halo:
        ring = cv2.dilate(glyph, np.ones((9, 9), np.uint8)) > 0
        image[ring] = 250
    image[glyph > 0] = 10
    return image, (glyph > 0).astype(np.uint8), cv2.dilate(glyph, np.ones((9, 9), np.uint8)) > 0


class _Truth:
    """A model that recovers the true art wherever it is asked to."""

    def __init__(self, truth):
        self.truth = truth

    def reconstruct(self, image, mask):
        out = image.copy()
        out[mask > 0] = self.truth[mask > 0]
        return out, {}


def _fill(monkeypatch, truth, image, mask):
    monkeypatch.setattr(ob.advanced_art_inpainting, "get_default_inpainter", lambda: _Truth(truth))
    ob._LEARNED_FILL_CACHE.clear()
    group = types.SimpleNamespace(box=(30, 40, 150, 50), background_metrics={})
    return ob._learned_inpaint(image, group, mask)


def test_halo_around_glyphs_joins_the_mask_but_stays_bounded():
    truth = _stripes()
    image, glyph, halo = _text_on(truth, halo=True)
    grown = ob._measured_halo_mask(image, glyph)
    assert (grown[halo] > 0).mean() > 0.95
    reach = cv2.distanceTransform((glyph == 0).astype(np.uint8), cv2.DIST_L2, 3)
    assert reach[grown > 0].max() <= 9.5


def test_no_halo_means_no_growth_beyond_the_fringe():
    truth = _stripes()
    image, glyph, _ = _text_on(truth, halo=False)
    grown = ob._measured_halo_mask(image, glyph)
    reach = cv2.distanceTransform((glyph == 0).astype(np.uint8), cv2.DIST_L2, 3)
    assert reach[grown > 0].max() <= 5.5


def test_local_halo_measurement_matches_full_page_result():
    image = np.full((900, 1200, 3), 130, np.uint8)
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.putText(mask, "ABC", (430, 470), cv2.FONT_HERSHEY_DUPLEX, 2.0, 1, 4)
    image[cv2.dilate(mask, np.ones((9, 9), np.uint8)) > 0] = 245
    image[mask > 0] = 10
    expected = ob._measured_halo_mask_local(image, mask, 8, 30)
    actual = ob._measured_halo_mask(image, mask)
    assert np.array_equal(actual, expected)


def test_textured_art_leaves_no_halo_ghost_after_the_fill(monkeypatch):
    truth = _stripes()
    image, glyph, halo = _text_on(truth, halo=True)
    out = _fill(monkeypatch, truth, image, glyph)
    region = cv2.dilate(glyph, np.ones((11, 11), np.uint8)) > 0
    error = np.abs(out.astype(int) - truth.astype(int)).mean(axis=2)[region]
    assert error.mean() < 3.0
    ring = region & ~(glyph > 0)
    assert abs(float(out[ring].mean()) - float(truth[ring].mean())) < 5.0


def test_flat_art_without_halo_is_reconstructed_exactly(monkeypatch):
    truth = np.full((120, 220, 3), 200, np.uint8)
    image, glyph, _ = _text_on(truth, halo=False)
    out = _fill(monkeypatch, truth, image, glyph)
    region = cv2.dilate(glyph, np.ones((7, 7), np.uint8)) > 0
    assert np.abs(out.astype(int) - truth.astype(int))[region].max() <= 1
    far = ~(cv2.dilate(glyph, np.ones((15, 15), np.uint8)) > 0)
    assert np.array_equal(out[far], image[far])
