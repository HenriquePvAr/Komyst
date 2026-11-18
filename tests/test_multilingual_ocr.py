"""Multi-language OCR: per-language model profiles and script-aware line/group rules."""
import numpy as np

from komyst.ocr import ocr_balloon as ob
from komyst.ocr import rapidocr_profiles as rp
from komyst.ocr.ocr_engine import clean_ocr_text


def test_ocr_zero_in_alphabetic_token_is_normalized_without_word_list():
    assert clean_ocr_text("IT'S TO0 OBVIOUS. NOT TO0 SHABBY.") == "IT'S TOO OBVIOUS. NOT TOO SHABBY."
    assert clean_ocr_text("B0OK R2D2 AB02 A0") == "BOOK R2D2 AB02 A0"
    assert clean_ocr_text("記憶0喪失") == "記憶0喪失"


def test_language_choices_map_to_profiles_and_missing_models_keep_the_bundled_engine(tmp_path, monkeypatch):
    assert rp.normalize_lang("2") == "ko" and rp.normalize_lang("japones") == "ja"
    assert rp.normalize_lang("3") == "en" and rp.normalize_lang("rapidocr") == ""
    monkeypatch.setattr(rp, "models_root", lambda: tmp_path)
    assert rp.profile_for("2") is None  # no model files: the bundled engine reads it
    folder = tmp_path / "v5_mobile"
    folder.mkdir()
    for name in ("ch_PP-OCRv5_det_mobile.onnx", "korean_PP-OCRv5_rec_mobile.onnx"):
        (folder / name).write_bytes(b"x")
    assert rp.profile_for("ko").name == "ppocrv5_mobile_korean"
    assert rp.profile_for("3") is None  # English stays bundled unless its profile is chosen
    tiny = tmp_path / "v6"
    tiny.mkdir()
    for name in ("PP-OCRv6_det_tiny.onnx", "PP-OCRv6_rec_tiny.onnx"):
        (tiny / name).write_bytes(b"x")
    assert rp.profile_for("es").name == "ppocrv6_tiny"  # Spanish accents need PP-OCRv6


def test_hangul_lines_are_not_noise_but_vowelless_latin_still_is():
    def reason(text):
        line = ob.OCRLine(text=text, confidence=0.95, polygon=np.zeros((4, 2)), box=(10, 10, 200, 40), raw_text=text)
        return ob._line_ignore_reason(line, (2000, 800, 3))
    assert reason("올해 세 살이었지?") == ""
    assert reason("BRRRZT") == "noise_like_text"


def test_profile_engine_keeps_the_rapidocr_1x_call_shapes():
    class Output:
        def __init__(self, boxes, txts, scores):
            self.boxes, self.txts, self.scores = boxes, txts, scores

    engine = rp.RapidOCRProfileEngine.__new__(rp.RapidOCRProfileEngine)
    engine._engine = lambda image, **kw: (Output(None, ["줄"], [0.9]) if kw.get("use_det") is False
                                          else Output([[[0, 0], [4, 0], [4, 2], [0, 2]]], ["줄"], [0.8]))
    page, _ = engine(np.zeros((4, 4, 3), np.uint8), use_cls=False)
    crop, _ = engine(np.zeros((4, 4, 3), np.uint8), use_det=False, use_cls=False, use_rec=True)
    assert page[0][1:] == ["줄", 0.8] and len(page[0]) == 3
    assert crop == [["줄", 0.9]]


def _line(text, box):
    return ob.OCRLine(text=text, confidence=0.95, polygon=np.zeros((4, 2)), box=box, raw_text=text)


def test_vertical_japanese_columns_read_right_to_left_and_join_one_balloon():
    right = _line("覚えて", (200, 100, 40, 130))
    left = _line("ない", (150, 100, 40, 80))  # a short, nearly square column
    assert [l.text for l in ob.reading_order([left, right])] == ["覚えて", "ない"]
    group = ob.TextGroup(group_id="G", lines=[right], text=right.text)
    assert ob._line_belongs_to_group(left, group)


def test_two_kana_are_a_word_but_two_latin_letters_are_noise():
    assert ob._line_ignore_reason(_line("ない", (10, 10, 40, 80)), (2000, 800, 3)) == ""
    assert ob._line_ignore_reason(_line("xq", (10, 10, 40, 20)), (2000, 800, 3)) == "noise_like_text"


def test_tile_cut_fragment_of_a_longer_reading_is_dropped():
    from komyst.ocr.ocr_engine import _deduplicate_tiled_ocr_lines
    whole = _line("しましょう", (100, 100, 40, 200))
    fragment = _line("しま", (100, 100, 40, 80))
    other = _line("ではこう", (160, 100, 40, 160))
    kept, dropped = _deduplicate_tiled_ocr_lines([whole, fragment, other])
    assert [l.text for l in kept] == ["しましょう", "ではこう"] and dropped == 1


def test_vertical_column_width_sets_the_font_size_above_the_global_cap():
    from komyst.config import settings as config
    image = np.full((1400, 1400, 3), 255, np.uint8)
    image[300:900, 640:740] = 0  # one wide vertical column on a high-resolution raw
    column = _line("わからない", (630, 290, 120, 620))
    group = ob.TextGroup(group_id="G", lines=[column], text=column.text, translation="Não sei")
    ob._draw_group_translation(image.copy(), group, font_path=None, source_bgr=image)
    assert group.font_size > config.MAX_FONT_SIZE  # sized from the 120 px column, not capped at the default


def test_russian_and_french_profiles_and_canonical_models_root(tmp_path, monkeypatch):
    from komyst.runtime import runtime_paths

    assert rp.normalize_lang("ru") == "ru" and rp.normalize_lang("fr") == "fr"
    monkeypatch.delenv("KOMYST_OCR_MODELS_DIR", raising=False)
    rapid_dir = tmp_path / "models" / "rapidocr"
    v5 = rapid_dir / "v5_mobile"
    v5.mkdir(parents=True)
    monkeypatch.setattr(runtime_paths, "models_root", lambda: tmp_path / "models")
    assert rp.models_root() == rapid_dir
    for name in ("ch_PP-OCRv5_det_mobile.onnx", "eslav_PP-OCRv5_rec_mobile.onnx", "latin_PP-OCRv5_rec_mobile.onnx"):
        (v5 / name).write_bytes(b"x")
    assert rp.profile_for("ru").name == "ppocrv5_mobile_eslav"
    assert rp.profile_for("fr").name == "ppocrv5_mobile_latin"


def test_non_english_prose_is_eligible_for_learned_last_resort_cleanup():
    for text in (
        "백표아이의 성별을 몰라?",
        "あの涙の跡―何か精神的なショック",
        "ПРИВЕТ, МИР! ЭТО ТЕСТ.",
        "¡¿QUÉ ESTÁS HACIENDO AQUÍ?!",
    ):
        line = _line(text, (20, 20, 180, 60))
        group = ob.TextGroup(group_id="G", lines=[line], text=text, classification="speech", translation="Tradução")
        assert ob._last_resort_allowed(group) is True, f"expected last resort allowed for {text!r}"

    sign_line = _line("ASSISTANCE", (20, 20, 180, 60))
    sign_group = ob.TextGroup(group_id="S", lines=[sign_line], text="ASSISTANCE", classification="speech", translation="Assistência")
    assert ob._last_resort_allowed(sign_group) is False


def test_english_glued_word_splitter_preserves_non_english_latin_words():
    spanish = "CONTIGO ESTAREMOS SIEMPRE, HERMANO."
    assert ob.split_glued_source_words(spanish, ocr_lang="es") == spanish
    assert ob.split_glued_source_words("WEPLANTO STAY", ocr_lang="en") == "WE PLAN TO STAY"


def test_post_render_source_text_check_catches_surviving_cjk_glyphs(monkeypatch):
    class FakeEngine:
        def __init__(self, lang, **_kw):
            self.lang = lang

        def _detect_with_rapidocr(self, _crop):
            if self.lang == "ja":
                return [_line("癒えた", (4, 4, 30, 80))]
            return [_line("Mas cicatrizou", (10, 10, 120, 30))]

    monkeypatch.setattr(ob, "OCREngine", FakeEngine)
    src_line = _line("癒えたけど", (10, 10, 40, 120))
    group = ob.TextGroup(
        group_id="G1",
        lines=[src_line],
        text="癒えたけど",
        classification="speech",
        translation="Mas cicatrizou",
    )
    group.safe_area = (10, 10, 140, 140)
    rendered = np.full((200, 200, 3), 255, dtype=np.uint8)
    summary = ob._post_render_source_text_check(rendered, group, page_index=6, original_bgr=rendered)
    assert summary["passed"] is False
    assert summary["residual_source_tokens"]
