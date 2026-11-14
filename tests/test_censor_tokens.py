"""Censored words stay censored through translation."""
from komyst.translation import censor_tokens


def test_censored_tokens_round_trip_through_placeholders():
    text, tokens = censor_tokens.protect("YET THAT B**** SEEMS FINE, WHAT THE F*CK.")
    assert "*" not in text and tokens == ["B****", "F*CK"]
    translated = "MAS AQUELE [1] PARECE BEM, QUE [2]."
    assert censor_tokens.restore(translated, tokens) == "MAS AQUELE B**** PARECE BEM, QUE F*CK."


def test_text_without_censoring_is_untouched():
    assert censor_tokens.protect("NOTHING HERE 2 * 3")[1] == []
    assert censor_tokens.restore("ALGO [1]", []) == "ALGO [1]"


def test_backend_provider_keeps_censoring(tmp_path, monkeypatch):
    from komyst.translation.providers.komyst_backend_provider import KomystBackendTranslationProvider, MockBackendClient

    provider = KomystBackendTranslationProvider(runtime_root=tmp_path, backend=MockBackendClient())
    seen = []
    monkeypatch.setattr(provider, "_translate_many_unprotected",
                        lambda texts, force=False: seen.extend(texts) or [t.replace("THAT", "AQUELE") for t in texts])
    assert provider.translate_many(["THAT B**** IS FINE"]) == ["AQUELE B**** IS FINE"]
    assert seen == ["THAT [1] IS FINE"]
