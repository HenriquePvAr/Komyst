"""Stage 2: ROI rendering/validation parity, streaming PDF, CJK vertical tile merge, re-OCR prefilter, and short SFX."""
from unittest import mock

import cv2
import numpy as np
from PIL import Image

from komyst.config import settings as config
from komyst.export import pdf as pdf_export
from komyst.ocr import ocr_balloon as ob
from komyst.ocr.ocr_engine import OCRLine, _deduplicate_tiled_ocr_lines
import komyst.pipeline.benchmark_pipeline as pipeline


def _line(text, box, conf=0.95):
    x, y, w, h = box
    poly = np.asarray([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float32)
    return OCRLine(text=text, confidence=conf, polygon=poly, box=box, raw_text=text)


def test_roi_draw_occupancy_and_visual_bounds_match_and_stay_fast():
    page = np.full((2400, 1800, 3), 242, dtype=np.uint8)
    cv2.rectangle(page, (500, 400), (920, 760), (255, 255, 255), -1)
    cv2.rectangle(page, (500, 400), (920, 760), (20, 20, 20), 4)
    line = _line("WE HAVE TO MOVE NOW!", (540, 470, 340, 180))
    group = ob.TextGroup(
        group_id="G1",
        lines=[line],
        text=line.text,
        classification="speech",
        translation="Temos que sair daqui agora mesmo!",
    )
    mask = np.zeros(page.shape[:2], dtype=np.uint8)
    mask[450:680, 525:895] = 255

    rendered = ob._draw_group_translation(page, group, font_path=None, source_bgr=page)
    assert rendered.shape == page.shape
    # Outside the balloon neighbourhood, zero pixels may differ.
    assert np.array_equal(rendered[:300, :], page[:300, :])
    assert np.array_equal(rendered[900:, :], page[900:, :])

    occ = ob._translated_text_occupancy_metrics(page, rendered, group)
    assert occ["translated_text_pixels"] > 0
    assert 0.0 < occ["translated_text_box_occupancy_ratio"] <= 1.0

    allowed = ob._draw_allowed_group_mask(page.shape, group, cleanup_mask=mask)
    validated, summary = ob._enforce_visual_bounds(
        page, rendered, allowed, group=group, mask_metrics={"mask_to_text_area_ratio": 1.15}
    )
    assert summary["visual_validation_passed"] is True
    assert summary["changed_pixels_outside_mask"] == 0
    assert np.array_equal(validated, rendered)

    # Inject an unauthorized streak outside the allowed mask and verify rejection + distance metric.
    leaked = rendered.copy()
    leaked[200:205, 200:320] = 0
    rolled_back, bad_summary = ob._enforce_visual_bounds(
        page, leaked, allowed, group=group, mask_metrics={"mask_to_text_area_ratio": 1.15}
    )
    assert bad_summary["visual_validation_passed"] is False
    assert bad_summary["largest_outside_component_area"] == 5 * 120
    assert bad_summary["max_outside_distance_from_allowed_mask"] is not None
    assert np.array_equal(rolled_back, page)


def test_streaming_pdf_export_limits_simultaneous_open_rgb_pages(tmp_path, monkeypatch):
    paths = []
    for idx in range(6):
        p = tmp_path / f"p_{idx:02d}.png"
        Image.fromarray(np.full((400, 300, 3), idx * 30, dtype=np.uint8)).save(p)
        paths.append(p)

    real_to_rgb = pdf_export.to_rgb
    live_ids: set[int] = set()
    peak_live = 0

    def tracked_to_rgb(img):
        nonlocal peak_live
        rgb = real_to_rgb(img)
        obj_id = id(rgb)
        live_ids.add(obj_id)
        peak_live = max(peak_live, len(live_ids))
        orig_close = rgb.close

        def closing():
            live_ids.discard(obj_id)
            return orig_close()

        rgb.close = closing
        return rgb

    monkeypatch.setattr(pdf_export, "to_rgb", tracked_to_rgb)
    out_pdf = tmp_path / "chapter.pdf"
    pdf_export.generate_pdf(paths, out_pdf)
    assert out_pdf.is_file() and out_pdf.stat().st_size > 1000
    assert peak_live <= 2, f"expected streaming PDF save (<=2 live RGB images), got peak={peak_live}"
    assert len(live_ids) == 0


def test_megapixel_aware_auto_page_workers_scales_down_on_huge_pages(monkeypatch):
    fake_mem = mock.Mock(available=int(7.2 * (2**30)))
    monkeypatch.setattr("os.cpu_count", lambda: 12)
    with mock.patch("psutil.virtual_memory", return_value=fake_mem):
        assert pipeline._auto_page_workers(max_page_pixels=1_200_000) == 2
        assert pipeline._auto_page_workers(max_page_pixels=12_000_000) == 1


def test_vertical_cjk_tile_boundary_overlap_merges_without_repeating_overlap_chars():
    upper = _line("約束を守", (200, 800, 40, 180), conf=0.94)
    lower = _line("を守るから", (202, 910, 40, 170), conf=0.92)
    neighbour = _line("次の場所へ", (140, 800, 40, 210), conf=0.96)
    kept, dropped = _deduplicate_tiled_ocr_lines([upper, lower, neighbour])
    texts = [ln.text for ln in kept]
    assert "約束を守るから" in texts
    assert "次の場所へ" in texts
    assert len(kept) == 2
    assert dropped >= 1


def test_masked_page_rediscovery_skips_full_ocr_when_painted_page_has_no_uncovered_ink(monkeypatch):
    page = np.full((600, 500, 3), 250, dtype=np.uint8)
    page[110:145, 110:340] = 20
    existing = [_line("HELLO THERE", (105, 105, 245, 45))]

    called = []

    class FakeEngine:
        engine = "rapidocr"

        def detect_lines(self, *_a, **_kw):
            called.append(True)
            return []

    monkeypatch.setattr(ob, "_reocr_engines_for", lambda *_a, **_kw: [FakeEngine()])
    out_lines, record = ob._masked_page_rediscovery(page, existing, "en", page_index=1)
    assert out_lines == existing
    assert called == []
    assert record["accepted"] is False


def test_short_expressive_manga_sfx_obeys_translate_sfx_toggle():
    for sfx_text in ("GRAAA AAAAA", "WooooOSH", "GLP.", "THNK"):
        grp = ob.TextGroup(group_id="G", lines=[_line(sfx_text, (40, 40, 120, 45))], text=sfx_text, classification="speech")
        with mock.patch.object(config, "TRANSLATE_SFX", False):
            ob._apply_classification_policy(grp)
        assert grp.ignored is True and grp.ignore_reason == "sfx_translation_disabled", f"expected SFX disabled for {sfx_text!r}"

        grp_on = ob.TextGroup(group_id="G2", lines=[_line(sfx_text, (40, 40, 120, 45))], text=sfx_text, classification="speech")
        with mock.patch.object(config, "TRANSLATE_SFX", True):
            ob._apply_classification_policy(grp_on)
        assert grp_on.ignored is False, f"expected translatable when TRANSLATE_SFX=True for {sfx_text!r}"

    # Real short dialogue words and multi-syllable names must NOT be suppressed when TRANSLATE_SFX=False.
    for dialogue in ("WAIT!", "STOP!", "WHAT?!", "NO!", "KENJI"):
        dlg = ob.TextGroup(group_id="D", lines=[_line(dialogue, (40, 40, 120, 45))], text=dialogue, classification="speech")
        with mock.patch.object(config, "TRANSLATE_SFX", False):
            ob._apply_classification_policy(dlg)
        assert dlg.ignored is False, f"dialogue/name {dialogue!r} must stay translatable"

    # A 3-letter sound or stretched scream returned unchanged by provider closes as preserved lettering, not failure.
    for kept_sound in ("GLP.", "Guh.", "GRAAA AAAAA"):
        g_fail = ob.TextGroup(group_id="F", lines=[_line(kept_sound, (40, 40, 120, 45))], text=kept_sound, classification="speech")
        ob._finalize_translation_failure(g_fail, "untranslated_source_after_retries", candidate=kept_sound)
        assert g_fail.manual_review_required is False
        assert g_fail.translation_final_state == "preserved_original"
        assert g_fail.translation_final_reason == "sfx_original_lettering_kept"
