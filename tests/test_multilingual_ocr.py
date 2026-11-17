"""Multi-language OCR: per-language model profiles and script-aware line/group rules."""
import numpy as np
from types import SimpleNamespace

from komyst.ocr import ocr_balloon as ob
from komyst.ocr import rapidocr_profiles as rp
from komyst.ocr.ocr_engine import clean_ocr_text


def test_ocr_zero_in_alphabetic_token_is_normalized_without_word_list():
    assert clean_ocr_text("IT'S TO0 OBVIOUS. NOT TO0 SHABBY.") == "IT'S TOO OBVIOUS. NOT TOO SHABBY."
    assert clean_ocr_text("B0OK R2D2 AB02 A0") == "BOOK R2D2 AB02 A0"
    assert clean_ocr_text("記憶0喪失") == "記憶0喪失"


def test_clear_multiword_display_title_promotes_without_repeated_sound():
    def group(text):
        return SimpleNamespace(
            text=text, classification="decorative", preserve_as_name=False,
            quality_reasons=[], confidence=0.941, main_text_score=0.34,
            background_type="textured_art", detected_proper_names=[],
            background_metrics={"context_saturation_mean": 154,
                                "context_dark_pixel_ratio": 0.72,
                                "context_white_pixel_ratio": 0.06},
        )
    assert ob._decorative_short_display_story_promotion_allowed(group("RADIANT SILVER WINGS"))
    assert not ob._decorative_short_display_story_promotion_allowed(group("BOOM BOOM BOOM"))


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
