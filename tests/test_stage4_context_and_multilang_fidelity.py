"""Stage 4: DeepL scene context, idempotent wallet-reserve retry, single-syllable CJK speech, and non-English semantic fidelity."""
import numpy as np

from komyst.ocr import ocr_balloon as ob
from komyst.ocr.ocr_engine import OCRLine
from komyst.translation import portuguese_words, semantic_fidelity
from komyst.translation.providers import komyst_backend_provider as kbp


def test_wallet_reserve_retries_transient_transport_failure(monkeypatch):
    calls = 0

    def flaky_transport(path, payload, token):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError("temporary socket reset")
        return {"reservation_id": "11111111-1111-1111-1111-111111111111"}

    monkeypatch.setattr(kbp.time, "sleep", lambda _s: None)
    client = kbp.HttpBackendClient("https://example.supabase.co", transport=flaky_transport)
    res = client.reserve(job_id="job-1", request_id="req-1", auth_token="tok", device_id="22222222-2222-2222-2222-222222222222")
    assert res["reservation_id"] == "11111111-1111-1111-1111-111111111111"
    assert calls == 3


def test_translate_batch_includes_bounded_scene_context(monkeypatch):
    captured: dict = {}

    def spy_transport(path, payload, token):
        captured["path"] = path
        captured["payload"] = dict(payload)
        return {
            "request_id": payload["request_id"],
            "status": "completed",
            "items": [{"item_id": i["item_id"], "translated_text": f"PT:{i['text']}"} for i in payload["items"]],
        }

    monkeypatch.setenv("KOMYST_DEVICE_UUID", "33333333-3333-3333-3333-333333333333")
    client = kbp.HttpBackendClient("https://example.supabase.co", transport=spy_transport)
    items = (kbp.BatchItem("i1", "안녕하세요"), kbp.BatchItem("i2", "반갑습니다"))
    ctx = kbp._build_batch_scene_context(items, items, max_chars=200)
    req = kbp.BatchRequest("req-ctx", "job-ctx", "KO", "PT-BR", items, context=ctx)
    resp = client.translate_batch(
        req,
        reservation_id="44444444-4444-4444-4444-444444444444",
        auth_token="tok",
    )
    assert len(resp.items) == 2
    assert captured["payload"]["context"] == "안녕하세요 | 반갑습니다"


def test_single_syllable_non_latin_acknowledgements_are_kept_and_not_weak():
    for txt in ("예,", "예.", "네!", "え?", "好!"):
        line = OCRLine(text=txt, confidence=0.92, polygon=np.zeros((4, 2), dtype=np.float32), box=(20, 20, 48, 42), raw_text=txt)
        assert ob._line_ignore_reason(line, (2000, 800, 3)) == "", f"expected {txt!r} not to be ignored"
        assert ob._looks_like_noise(txt) is False, f"expected {txt!r} not to be dropped as noise"
        assert ob._is_weak_ocr_line(line) is False, f"expected {txt!r} not to trigger weak-line re-OCR"


def test_non_english_fidelity_does_not_reject_valid_subordinating_clauses_or_romanized_nouns():
    # Korean/Spanish subordinating clauses ("Depois de...", "até que...") have no English "after"/"until" token.
    ko_finding = semantic_fidelity.evaluate_local_fidelity(
        "대표가 된 후,",
        "Depois de se tornar o representante,",
        source_lang="ko",
    )
    assert ko_finding.faithful is True

    es_finding = semantic_fidelity.evaluate_local_fidelity(
        "Después de llegar a la ciudad,",
        "Depois de chegar à cidade,",
        source_lang="es",
    )
    assert es_finding.faithful is True

    # Numeric quantity invariant MUST still block across every language.
    bad_num = semantic_fidelity.evaluate_local_fidelity(
        "3일 후",
        "Depois de 30 dias",
        source_lang="ko",
    )
    assert bad_num.status == semantic_fidelity.BLOCKED
    assert bad_num.primary_reason == semantic_fidelity.QUANTITY_CHANGED

    # Capitalized romanizations from non-Latin scripts must not trigger unknown_target_words retries,
    # while lowercase Portuguese typos still do.
    assert portuguese_words.unknown_target_words("Senhor Hyeonwoo chegou cedo.", "현우 님이 일찍 도착했습니다.") == []
    assert "ESTOVA" in portuguese_words.unknown_target_words("Ele estova esperando cedo.", "그가 일찍 기다리고 있었다.")
