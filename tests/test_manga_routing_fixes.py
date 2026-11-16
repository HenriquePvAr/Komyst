"""Regressions found on a black-and-white manga chapter (no provider, no models)."""
import numpy as np

from komyst.ocr import ocr_balloon as ob
from komyst.translation import portuguese_words as pw
from komyst.translation.semantic_fidelity import _malformed_portuguese
from tests.test_proper_name_routing import _group


def test_authorized_halo_counts_as_allowed_page_change():
    group = _group("HELLO THERE.", classification="speech")
    extension = np.zeros((40, 40), bool)
    extension[5:8, 5:8] = True
    group.authorized_fill_extension = extension
    mask = ob._draw_allowed_group_mask((40, 40, 3), group, cleanup_mask=np.zeros((40, 40), np.uint8))
    assert mask[6, 6] == 255 and mask[20, 20] == 0


def test_glued_words_are_counted_as_words_for_translation_routing():
    group = _group("REMEMBER GETTINGINTO ADRINKING CONTEST WITH SOMESTRANGE OLDGUY, ANDTHEN.. NOTHIN'.",
                   classification="narration")
    group.quality_score = 0.0
    group.quality_reasons = ["compact_word_segmentation_candidate", "dictionary_near_miss"]
    assert ob.ocr_suspicious_but_translatable(group)


def test_spacing_only_reads_agree_but_word_boundaries_still_matter():
    sig = lambda text: ob._source_recovery_word_signature(ob.split_glued_source_words(text))
    assert sig("WHAT YOU LACK IN HEIGHT, YOUMAKE UP") == sig("WHAT YOU LACK IN HEIGHT YOU MAKE UP")
    assert sig("THE RAPIST") != sig("THERAPIST")


def test_diminutive_and_translated_common_words_are_not_restored_to_english():
    assert pw.unknown_target_words("QUE INSETOZINHO!", "WHAT A LITTLE INSECT.") == []
    assert pw.restore_corrupted_source_words(
        "ENQUANTO VOCE ESTIVER DISTRATADO", "WHILE YOU ARE DISTRACTED", ["DISTRATADO"]
    ) == "ENQUANTO VOCE ESTIVER DISTRATADO"
    assert pw.restore_corrupted_source_words("O GEENOM VEIO", "GEHENNA CAME", ["GEENOM"]) == "O GEHENNA VEIO"


def test_personal_infinitive_is_grammatical_bare_infinitive_is_not():
    assert _malformed_portuguese("É MELHOR VOCÊ FICAR LONGE DA MINHA IRMÃ.") == ""
    assert _malformed_portuguese("PARA VOCÊ VER") == ""
    assert _malformed_portuguese("SE VOCÊ FAZER ISSO") == "voce fazer"


def _lettering(stroke):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (520, 140), (31, 31, 31))
    font = ImageFont.truetype("arialbd.ttf", 80)
    if stroke:
        ImageDraw.Draw(image).text((20, 20), "brain...", font=font, fill=(10, 10, 10),
                                   stroke_width=6, stroke_fill=(255, 255, 255))
    else:
        ImageDraw.Draw(image).text((20, 20), "BOOM!", font=font, fill=(255, 255, 255))
    return np.array(image)[:, :, ::-1].copy()


def test_dark_ink_with_white_outline_on_a_black_panel_keeps_dark_ink():
    group = _group("brain...")
    outlined = ob.extract_original_lettering_profile(_lettering(True), group, (10, 10, 500, 120), fill_ink=True)
    plain = ob.extract_original_lettering_profile(_lettering(False), group, (10, 10, 500, 120), fill_ink=True)
    assert outlined["color_family"] == "black" and min(outlined["stroke_color"]) >= 200
    assert plain["color_family"] == "white"


def test_caps_only_face_is_not_offered_for_mixed_case_text():
    from komyst.clean.ownership import font_fidelity as ff
    caps = [p for p in ff.raster_match_pool() if ff._caps_only(p)]
    if not caps:
        return
    masks = [("knew", np.ones((64, 160), bool))]
    best = ff.match_font_by_raster(masks, caps, draw_text="sabia")
    assert best is None


def test_common_short_word_stacked_on_a_text_line_is_kept_alone_it_is_noise():
    def candidate(text, box, ignored=False, reason=""):
        line = ob.OCRLine(text=text, confidence=0.78, polygon=np.zeros((4, 2)), box=box, raw_text=text)
        return ob.TextCandidate(line=line, ignored=ignored, ignore_reason=reason)
    stacked = [candidate("Up", (845, 851, 62, 44), True, "noise_like_text"),
               candidate("until now..", (794, 889, 133, 46))]
    alone = [candidate("Up", (845, 851, 62, 44), True, "noise_like_text"),
             candidate("until now..", (794, 1200, 133, 46))]
    ob._keep_short_words_stacked_on_text(stacked)
    ob._keep_short_words_stacked_on_text(alone)
    assert not stacked[0].ignored and alone[0].ignored


def test_object_pronoun_after_common_verb_is_split_not_corrected():
    assert ob.split_glued_source_words("Just cutit and hit") == "Just cut it and hit"
    assert ob.region_taxonomy.segment_words("SUMMONOR") is None


def test_place_names_recurring_names_and_glued_contractions_survive_repair():
    text = "TOO!I'MFROM RAYAKA VILLAGE, A LITTLE WAYS ABOVE HAGE."
    names = ob.chapter_recurring_tokens(["WELCOME TO HAGE", text])
    assert ob.split_glued_source_words(text, chapter_names=names) == (
        "TOO!I'M FROM RAYAKA VILLAGE, A LITTLE WAYS ABOVE HAGE.")


def test_shout_cut_into_scraps_is_joined_but_a_stutter_is_not():
    assert ob.split_glued_source_words("A WE SO ME!") == "AWESOME!"
    assert ob.split_glued_source_words("I I I CAN'T") == "I I I CAN'T"
    assert ob.split_glued_source_words("IT IS UP TO ME") == "IT IS UP TO ME"


def test_prose_whose_dots_the_ocr_dropped_may_use_the_learned_last_resort():
    group = _group("his kinetic Vision and his explosive power", classification="narration")
    sign = _group("GRAND OPENING", classification="narration")
    assert ob._last_resort_allowed(group) or not ob._group_has_story_translation_authority(group)
    assert not ob._last_resort_allowed(sign)


def test_glued_words_before_a_place_noun_split_when_they_end_in_a_determiner():
    assert ob.split_glued_source_words("THE NUNFROMMY VILLAGE!") == "THE NUN FROM MY VILLAGE!"
    assert ob.split_glued_source_words("FROM RAYAKA VILLAGE") == "FROM RAYAKA VILLAGE"


def test_camel_case_glue_splits_at_capitals():
    assert ob.split_glued_source_words("TheBlackBulls") == "The Black Bulls"
    assert ob.split_glued_source_words("YouTube") == "YouTube"


def test_dropped_punctuation_line_costs_no_ocr_quality():
    from tests.test_proper_name_routing import _line
    group = _group("IT'S GREAT TO MEETCHA", classification="narration")
    group.cleanup_lines = [_line("!!!")]
    assert "ignored_line_inside_text_region" not in ob.score_group_ocr_quality(group)[1]
    group.cleanup_lines = [_line("TO")]
    assert "ignored_line_inside_text_region" in ob.score_group_ocr_quality(group)[1]


def test_echoed_laughter_is_a_legitimate_preserve_but_a_sentence_is_not():
    assert ob._echo_is_name_shaped(_group("AH HA HA HA!", classification="narration"))
    assert not ob._echo_is_name_shaped(_group("I LOVE YOU SO MUCH", classification="narration"))


def test_missed_first_line_is_read_by_the_recognizer_not_assumed():
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (400, 260), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("comicbd.ttf", 34)  # serifed "I", as comic lettering draws it
    draw.text((170, 40), "I", font=font, fill=(0, 0, 0))
    draw.text((120, 95), "MEAN,", font=font, fill=(0, 0, 0))
    bgr = np.array(image)[:, :, ::-1].copy()
    line = ob.OCRLine(text="MEAN,", confidence=0.99, polygon=np.zeros((4, 2)),
                      box=(118, 92, 126, 42), raw_text="MEAN,")
    group = ob.TextGroup(group_id="G", lines=[line], text="MEAN,")
    ob._recover_missed_leading_lines([group], bgr)
    assert group.text == "I MEAN,"
    empty = ob.TextGroup(group_id="H", lines=[ob.OCRLine(text="MEAN,", confidence=0.99,
                         polygon=np.zeros((4, 2)), box=(118, 92, 126, 42), raw_text="MEAN,")], text="MEAN,")
    ob._recover_missed_leading_lines([empty], np.full_like(bgr, 255))
    assert empty.text == "MEAN,"


def test_art_strokes_read_as_letters_are_dropped_from_mixed_case_lettering():
    assert ob.split_glued_source_words("His well-trained Cbody's super reflexes..") == (
        "His well-trained body's super reflexes..")
    assert ob.split_glued_source_words("But his II.body...") == "But his body..."
    for keep in ("McDonald is here", "World War II ends", "I can do it", "It is an Apple phone"):
        assert ob.split_glued_source_words(keep) == keep


def test_name_gender_comes_from_the_chapter_pronouns_not_the_spelling():
    sources = ["Asta had cut through magic with his muscles", "Asta could not see it. He tried",
               "Noelle said she would come, her wand ready", "It's Asta!"]
    genders = pw.chapter_name_genders(sources, ["Asta", "Noelle"])
    assert genders == {"ASTA": "m", "NOELLE": "f"}
    assert pw.align_name_articles("É a Asta! O cérebro da Asta", genders) == "É o Asta! O cérebro do Asta"
    assert pw.align_name_articles("o Noelle", genders) == "a Noelle"
    assert pw.chapter_name_genders(["Kai said he and she left"], ["Kai"]) == {}


def test_two_everyday_words_glued_are_split_even_when_a_rare_word_is_one_edit_away():
    assert ob.split_glued_source_words("WAIT, ISHE DEAD...?") == "WAIT, IS HE DEAD...?"


def test_three_real_words_trailing_off_are_narration_not_a_label():
    from komyst.review import region_taxonomy as rt
    assert rt.weak_label_semantic_promotion_allowed("unknown", "But his body...")
    assert not rt.weak_label_semantic_promotion_allowed("unknown", "ROYAL MAGIC ACADEMY")


def test_one_subject_pronoun_genders_a_repeated_rare_name():
    sources = ["Asta had cut through magic with his muscles", "It's Asta!", "I'M ASTA FROM HAGE"]
    names = pw.chapter_name_candidates(sources)
    assert "ASTA" in names
    assert pw.chapter_name_genders(sources, names).get("ASTA") == "m"
