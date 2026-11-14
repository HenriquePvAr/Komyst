import numpy as np

from komyst.ocr.ocr_balloon import TextGroup, score_group_ocr_quality, split_glued_source_words
from komyst.ocr.ocr_engine import OCRLine, _repair_tokens_with_generic_vocabulary


def _score(text):
    line = OCRLine(text=text, confidence=0.95,
                   polygon=np.array([[10, 10], [210, 10], [210, 45], [10, 45]], dtype=np.int32),
                   box=(10, 10, 200, 35), raw_text=text, engine="rapidocr", page=1)
    group = TextGroup(group_id="T001", lines=[line], text=text, classification="speech",
                      inside_balloon_like_region=True, source_engine="rapidocr")
    return score_group_ocr_quality(group)


def test_vocabulary_misread_not_applied_to_hyphenated_name():
    text = "TOAN-KI IS HERE"
    assert split_glued_source_words(text, chapter_words=frozenset({"TOWN"})) == text
    # control: the same unhyphenated token is still corrected
    assert split_glued_source_words("TOAN IS HERE", chapter_words=frozenset({"TOWN"})) != "TOAN IS HERE"


def test_generic_vocab_repair_skips_hyphenated_name():
    for text in ("CAIN-RA", "MOON-JO", "CAIN-RA'S MANAGER"):
        assert _repair_tokens_with_generic_vocabulary(text)[0] == text


def test_hyphenated_name_not_penalized():
    _, reasons = _score("TOAN-KI'S MANAGER")
    assert "unknown_short_token_in_phrase" not in reasons
    assert "dictionary_near_miss" not in reasons


def test_glued_prefix_is_split_off_a_hyphenated_name():
    assert split_glued_source_words("OPPOSITEXY-ZED QUO") == "OPPOSITE XY-ZED QUO"
    assert split_glued_source_words("KINDOFTALKABOUTXY-ZED.") == "KIND OF TALK ABOUT XY-ZED."
    assert split_glued_source_words("BADMOUTHEDXY-ZED") == "BADMOUTHED XY-ZED"


def test_chapter_hyphenated_name_drives_the_cut():
    from komyst.ocr.ocr_balloon import chapter_hyphenated_names
    names = chapter_hyphenated_names(["XY-ZED HEARD.", "NO, XY-ZED!", "WELL-KNOWN WELL-KNOWN"])
    assert names == {"XY-ZED"}
    assert split_glued_source_words("OPPOSITEXY-ZED", chapter_names=names) == "OPPOSITE XY-ZED"


def test_surname_after_hyphenated_name_is_not_misread_corrected():
    assert split_glued_source_words("XY-ZED GWON", chapter_words=frozenset({"WON"})) == "XY-ZED GWON"


def test_real_hyphenated_compounds_are_untouched():
    for text in ("WELL-KNOWN", "SOMETHING-ELSE", "MOTHER-IN-LAW"):
        assert split_glued_source_words(text) == text
