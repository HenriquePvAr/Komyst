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
