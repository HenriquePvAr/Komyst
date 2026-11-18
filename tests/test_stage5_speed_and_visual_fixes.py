import test_support._test_bootstrap as _test_bootstrap  # noqa: F401

import threading
import types
import cv2
import numpy as np

import komyst.clean.ownership.font_fidelity as font_fidelity
import komyst.ocr.ocr_balloon as ob
import komyst.ocr.rapidocr_profiles as rp
from komyst.ocr.ocr_engine import OCRLine, clean_ocr_text
import komyst.runtime.hardware_profile as hp


def _mk_line(text, box, *, confidence=0.92, polygon=None):
    x, y, w, h = box
    poly = polygon if polygon is not None else [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return OCRLine(text=text, confidence=confidence, polygon=poly, box=box, raw_text=text)


def test_clean_ocr_text_strips_empty_parentheses_artifacts_only():
    assert clean_ocr_text("무신() 원하진()") == "무신 원하진"
    assert clean_ocr_text("천마（  ）강림") == "천마강림"
    assert clean_ocr_text("무신(武神)") == "무신(武神)"


def test_font_fidelity_resolve_font_uses_cached_hashes():
    font_fidelity._cached_file_sha256.cache_clear()
    _, first = font_fidelity.resolve_font("balloon_dialogue", 28, text="Olá mundo!")
    misses_after_first = font_fidelity._cached_file_sha256.cache_info().misses
    _, second = font_fidelity.resolve_font("balloon_dialogue", 28, text="Outra fala com acentuação!")
    info = font_fidelity._cached_file_sha256.cache_info()
    assert first["resolved_font_path"] == second["resolved_font_path"]
    assert first["font_file_hash"] == second["font_file_hash"]
    assert info.misses == misses_after_first
    assert info.hits >= 1


def test_legible_source_residual_infers_non_latin_lang_and_catches_short_hangul(monkeypatch):
    monkeypatch.setattr(ob.config, "CLEAN_RESIDUAL_OCR_CHECK", True)
    monkeypatch.setattr(ob, "_RESIDUAL_OCR_ENGINES", [])
    monkeypatch.setattr(ob, "_RESIDUAL_OCR_ENGINES_BY_LANG", {})
    requested_langs = []

    class _FakeKoreanEngine:
        engine = "fake_ko"

        def detect_lines(self, crop, **_kwargs):
            return [_mk_line("너무", (4, 4, 24, 14), confidence=0.88)]

    def fake_engines_for(lang, _errors):
        requested_langs.append(lang)
        return [_FakeKoreanEngine()]

    monkeypatch.setattr(ob, "_reocr_engines_for", fake_engines_for)
    line = _mk_line("너무", (20, 20, 32, 18), confidence=0.92)
    group = types.SimpleNamespace(
        text="너무",
        translation="Demais",
        ocr_lang=None,
        lines=[line],
        cleanup_lines=[line],
        box=(20, 20, 32, 18),
    )
    res = ob._legible_source_residual(np.full((80, 100, 3), 245, dtype=np.uint8), group)
    assert requested_langs == ["ko"]
    assert res["status"] == "legible"
    assert set(res["legible_source_tokens"]) >= {"너", "무"}


def test_measured_halo_and_outline_residue_capture_soft_glow_on_dark_backdrop():
    canvas = np.full((180, 260, 3), 6, dtype=np.uint8)
    glyph = np.zeros((180, 260), dtype=np.uint8)
    cv2.putText(glyph, "GLOW", (45, 105), cv2.FONT_HERSHEY_SIMPLEX, 1.4, 1, 4, cv2.LINE_AA)
    soft_glow = cv2.GaussianBlur((glyph * 255).astype(np.float32), (0, 0), 5.2)
    canvas_f = np.clip(6.0 + soft_glow * 0.95, 0, 255).astype(np.uint8)
    image = cv2.merge([canvas_f, canvas_f, canvas_f])
    image[glyph > 0] = 250

    grown_halo = ob._measured_halo_mask(image, glyph)
    dist = cv2.distanceTransform((glyph == 0).astype(np.uint8), cv2.DIST_L2, 3)
    mid_ring = (dist > 6.5) & (dist <= 10.5) & (canvas_f >= 20)
    assert np.any(mid_ring)
    assert float((grown_halo[mid_ring] > 0).mean()) >= 0.85

    group = types.SimpleNamespace(box=(35, 60, 190, 65), _fill_source_bgr=image)
    residue = ob._outline_residue_mask(group, glyph)
    assert residue is not None
    assert float(residue[mid_ring].mean()) >= 0.85


def test_balloon_border_mask_separates_touching_double_balloons():
    page = np.full((260, 220, 3), 252, dtype=np.uint8)
    # Two stacked white balloons separated by an anti-aliased grey/dark border (luma ~105)
    cv2.ellipse(page, (110, 75), (80, 52), 0, 0, 360, (105, 105, 105), 2, cv2.LINE_AA)
    cv2.ellipse(page, (110, 180), (80, 52), 0, 0, 360, (105, 105, 105), 2, cv2.LINE_AA)
    top_box = (65, 55, 90, 34)
    bot_box = (65, 160, 90, 34)
    lines = [_mk_line("첫 줄", top_box), _mk_line("둘째 줄", bot_box)]
    border = ob._balloon_border_mask(page, lines)
    group = types.SimpleNamespace(lines=[lines[1]])
    assert ob._border_separates(border, top_box, group) is True


def test_unenclosed_non_latin_sfx_disabled_when_translate_sfx_false(monkeypatch):
    monkeypatch.setattr(ob.config, "TRANSLATE_SFX", False)
    sfx_line = _mk_line(
        "피식",
        (80, 100, 54, 28),
        confidence=0.91,
        polygon=[(80, 112), (132, 98), (136, 122), (84, 134)],
    )
    sfx_group = types.SimpleNamespace(
        text="피식",
        lines=[sfx_line],
        box=(80, 100, 54, 28),
        classification="speech",
        background_type="textured_art",
        light_enclosure_interior=None,
        should_translate=True,
    )
    ob._apply_disabled_sfx_policy(sfx_group)
    assert sfx_group.classification == "sfx"
    assert sfx_group.ignored is True
    assert sfx_group.ignore_reason == "sfx_translation_disabled"

    # Enclosed 1-syllable dialogue inside a white balloon remains translatable
    enclosure = np.zeros((200, 200), dtype=bool)
    enclosure[40:150, 40:160] = True
    yes_line = _mk_line("예,", (75, 80, 38, 24), confidence=0.96)
    yes_group = types.SimpleNamespace(
        text="예,",
        lines=[yes_line],
        box=(75, 80, 38, 24),
        classification="speech",
        background_type="white_balloon",
        light_enclosure_interior=enclosure,
        ignored=False,
    )
    ob._apply_disabled_sfx_policy(yes_group)
    assert yes_group.ignored is False


def test_raster_font_choice_skips_non_latin_source_text(monkeypatch):
    called = False

    def boom(*_a, **_k):
        nonlocal called
        called = True
        raise AssertionError("should not run Latin raster match on non-Latin glyphs")

    monkeypatch.setattr(font_fidelity, "source_line_masks", boom)
    line = _mk_line("무림맹주가", (10, 10, 90, 26), confidence=0.95)
    group = types.SimpleNamespace(text="무림맹주가", lines=[line])
    assert ob._raster_font_choice(np.zeros((60, 120, 3), np.uint8), group, {}, "Líder da Aliança", None, "regular") is None
    assert called is False


def test_hardware_profile_includes_lama_infer_side_and_weak_notebook_leve():
    leve = hp.PROFILE_VALUES["leve"]
    assert leve["PIPELINE_PAGE_WORKERS"] == "1"
    assert leve["LAMA_MAX_INFER_SIDE"] == "576"
    assert leve["FONT_RASTER_MATCH"] == "0"
    assert hp.PROFILE_VALUES["equilibrado"]["LAMA_MAX_INFER_SIDE"] == "768"
    assert hp.PROFILE_VALUES["qualidade"]["LAMA_MAX_INFER_SIDE"] == "896"


def test_rapidocr_profile_engine_restores_use_det_after_rec_only_call():
    class _StatefulFakeRapidOCR:
        def __init__(self):
            self.use_det = True
            self.use_cls = False
            self.use_rec = True

        def __call__(self, _img, use_det=None, use_cls=None, use_rec=None):
            if use_det is not None:
                self.use_det = use_det
            if use_cls is not None:
                self.use_cls = use_cls
            if use_rec is not None:
                self.use_rec = use_rec
            if not self.use_det:
                return types.SimpleNamespace(boxes=None, txts=["너무"], scores=[0.95])
            return types.SimpleNamespace(
                boxes=[[[0, 0], [40, 0], [40, 20], [0, 20]]],
                txts=["무림맹주가"],
                scores=[0.97],
            )

    wrapper = rp.RapidOCRProfileEngine.__new__(rp.RapidOCRProfileEngine)
    wrapper._call_lock = threading.Lock()
    wrapper._engine = _StatefulFakeRapidOCR()

    rec_only, _ = wrapper(np.zeros((24, 48, 3), np.uint8), use_det=False)
    assert rec_only == [["너무", 0.95]]
    full_det, _ = wrapper(np.zeros((100, 100, 3), np.uint8))
    assert full_det is not None and full_det[0][1] == "무림맹주가"


def test_spanish_and_french_accents_and_elisions_do_not_trigger_english_ocr_corruption():
    import komyst.review.region_taxonomy as rt

    es_text = "POR ESO CREÍ QUE ERA AMOR Y ME ENAMORÉ DE ÉL AL INSTANTE."
    es_line = _mk_line(es_text, (20, 20, 300, 80), confidence=0.97)
    es_line.ocr_lang = "es"
    es_group = ob.TextGroup(group_id="ES1", lines=[es_line], text=es_text)
    es_group.ocr_lang = "es"
    score, reasons = ob.score_group_ocr_quality(es_group)
    assert score >= 0.95
    assert reasons == []

    fr_text = "L'HOMME QU'IL AVAIT ÉTÉ N'EXISTAIT PLUS."
    fr_line = _mk_line(fr_text, (20, 20, 300, 80), confidence=0.96)
    fr_line.ocr_lang = "fr"
    fr_group = ob.TextGroup(group_id="FR1", lines=[fr_line], text=fr_text)
    fr_group.ocr_lang = "fr"
    fr_score, fr_reasons = ob.score_group_ocr_quality(fr_group)
    assert fr_score >= 0.95
    assert fr_reasons == []

    assert rt.weak_label_semantic_promotion_allowed(
        "decorative", "A PESAR DE MI ANHELO, HERDIN NO ESTUVO PRESENTE.", source_lang="es"
    ) is True
    assert rt.weak_label_semantic_promotion_allowed("unknown", "CLAT", source_lang="es") is False

    valid, reason = ob.validate_translation_text(
        "ESTOY DISPUESTA A REPETIR ESTA NOCHE LAS VECES QUE HAGAN FALTA.",
        "ESTOU DISPOSTA A REPETIR ISSO ESTA NOITE QUANTAS VEZES FOR NECESSÁRIO.",
    )
    assert valid is True, reason


def test_vertical_cjk_three_columns_merge_despite_height_difference_and_y_jitter():
    page = np.full((600, 600, 3), 252, dtype=np.uint8)
    cv2.ellipse(page, (300, 300), (190, 210), 0, 0, 360, (20, 20, 20), 3)
    # Leftmost short column arrives slightly higher in y than middle column
    col_right = _mk_line("そして", (360, 180, 42, 220))
    col_mid = _mk_line("ここが", (300, 195, 42, 210))
    col_left = _mk_line("銀行!", (240, 185, 42, 82))
    groups = ob._group_lines([col_right, col_mid, col_left], image_bgr=page)
    assert len(groups) == 1
    assert groups[0].text == "そして ここが 銀行!"


def test_clamp_horizontal_span_prevents_side_by_side_vertical_balloon_overlap():
    # Left lobe at x=100..160, right lobe at x=300..360
    cl_left = ob._clamp_horizontal_span_to_neighbors(40, 340, 100, 100, 60, 280, [(300, 110, 60, 270)])
    cl_right = ob._clamp_horizontal_span_to_neighbors(120, 420, 300, 110, 60, 270, [(100, 100, 60, 280)])
    assert cl_left[1] < cl_right[0]


def test_english_quantity_ordinals_1s_ocr_speck_and_container_gap_interior_gate():
    import komyst.translation.semantic_fidelity as sf

    f1 = sf.evaluate_local_fidelity(
        "WAS HE PLANNING TO KILL THE NEWBIE ON DAY ONE?!",
        "ELE ESTAVA PLANEJANDO MATAR O NOVATO JÁ NO PRIMEIRO DIA?!",
        classification="speech",
        source_lang="en",
    )
    assert f1.status == sf.FAITHFUL, f1

    f2 = sf.evaluate_local_fidelity(
        "THIS 1S GREAT! YOU'RE SERIOUSLY INTERESTING!",
        "ISSO É ÓTIMO! VOCÊ É REALMENTE MUITO INTERESSANTE!",
        classification="speech",
        source_lang="en",
    )
    assert f2.status == sf.FAITHFUL, f2

    speck_txt = "ALL RIGHT, FOR THE SÉCOND BAPTISM, LET'S TRY TO KILL EACH OTHER."
    speck_line = _mk_line(speck_txt, (10, 10, 260, 60), confidence=0.95)
    speck_group = ob.TextGroup(group_id="SP1", lines=[speck_line], text=speck_txt)
    _, speck_reasons = ob.score_group_ocr_quality(speck_group)
    assert "non_ascii_ocr_artifact" not in speck_reasons

    assert ob._is_short_expressive_sfx_text("MUNCH MUINCH MUNCH MUINCH MUNCH") is True

    # Closed white balloon surrounded by dense cross-hatching outside the black border:
    # _speech_container_gap_boxes must NOT emit gap boxes for hatching outside the border.
    page = np.full((300, 300, 3), 245, dtype=np.uint8)
    for hx in range(20, 280, 10):
        cv2.rectangle(page, (hx, 20), (hx + 4, 38), (40, 40, 40), -1)
        cv2.rectangle(page, (hx, 240), (hx + 4, 258), (40, 40, 40), -1)
    cv2.ellipse(page, (150, 140), (95, 75), 0, 0, 360, (252, 252, 252), -1)
    cv2.ellipse(page, (150, 140), (95, 75), 0, 0, 360, (15, 15, 15), 4)
    inside_line = _mk_line("HELLO THERE", (95, 115, 110, 36))
    inside_line.metadata = {"visual_white_region_id": 1}
    gaps = ob._container_text_gap_boxes(page, [inside_line])
    assert gaps == []



