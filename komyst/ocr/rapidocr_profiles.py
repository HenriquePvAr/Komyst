"""Per-language RapidOCR models: each source language reads with the model that read it best.

Measured on real pages of this project (Korean Naver/MangaDex strips, Japanese raws with
vertical balloons, the English reference chapters), RapidOCR 3 with ONNX Runtime/DirectML:

* Korean   - PP-OCRv5 mobile detector + Korean PP-OCRv5 mobile recogniser: correct Hangul
             with word spaces, 0.32 s/page on DirectML. The bundled PP-OCRv4 model reads none.
* Japanese - PP-OCRv6 manga detector/recogniser pair: every sampled vertical line exact,
  Chinese    highest confidence; it also reads Chinese.
* English  - PP-OCRv6 tiny: 28-36 % faster than the bundled PP-OCRv4 on the reference chapters,
             with real word spaces (``OCR_ENGLISH_PROFILE=bundled`` keeps the old model).
* Spanish  - PP-OCRv6 tiny: reads the accents and ¿ ¡ (97 on a WEBTOON chapter; the bundled
             model read none), 31 % faster.

A language without a profile, or whose model files are missing, keeps the bundled engine.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from komyst.ocr import ocr_models

_LANG_ALIASES = {
    "1": "ja", "ja": "ja", "jpn": "ja", "japan": "ja", "japones": "ja",
    "2": "ko", "ko": "ko", "kor": "ko", "korean": "ko", "coreano": "ko",
    "zh": "zh", "ch": "zh", "chinese": "zh", "chines": "zh",
    "3": "en", "en": "en", "eng": "en", "ingles": "en",
    "es": "es", "spa": "es", "spanish": "es", "espanhol": "es", "latin": "es",
    "ru": "ru", "rus": "ru", "russian": "ru", "russo": "ru", "cyrillic": "ru",
    "fr": "fr", "fra": "fr", "french": "fr", "frances": "fr",
}


def normalize_lang(choice: str) -> str:
    return _LANG_ALIASES.get(str(choice or "").strip().lower(), "")


@dataclass(frozen=True)
class Profile:
    name: str
    folder: str
    files: tuple[str, ...]
    params: dict[str, Any]


def _manga_params(root: Path) -> dict[str, Any]:
    from rapidocr import OCRVersion

    return {
        "Det.model_path": str(root / "det" / "manga_det.onnx"),
        "Rec.model_path": str(root / "rec" / "manga_rec.onnx"),
        "Rec.rec_keys_path": str(root / "ppocrv6_dict.txt"),
        "Det.ocr_version": OCRVersion("PP-OCRv6"),
        "Rec.ocr_version": OCRVersion("PP-OCRv6"),
        # Manga lettering is thin and tightly packed: the model card's own thresholds.
        "Det.thresh": 0.15,
        "Det.box_thresh": 0.25,
        "Det.unclip_ratio": 1.5,
    }


def _profile(lang: str, english_profile: str) -> Profile | None:
    from rapidocr import LangRec, ModelType, OCRVersion

    if lang == "ko":
        return Profile("ppocrv5_mobile_korean", "v5_mobile",
                       ("ch_PP-OCRv5_det_mobile.onnx", "korean_PP-OCRv5_rec_mobile.onnx"),
                       {"Det.ocr_version": OCRVersion("PP-OCRv5"), "Det.model_type": ModelType("mobile"),
                        "Rec.ocr_version": OCRVersion("PP-OCRv5"), "Rec.model_type": ModelType("mobile"),
                        "Rec.lang_type": LangRec("korean")})
    if lang in {"ja", "zh"}:
        return Profile("ppocrv6_manga", "ppocrv6_manga",
                       ("det/manga_det.onnx", "rec/manga_rec.onnx", "ppocrv6_dict.txt"), {})
    if lang == "ru":
        return Profile("ppocrv5_mobile_eslav", "v5_mobile",
                       ("ch_PP-OCRv5_det_mobile.onnx", "eslav_PP-OCRv5_rec_mobile.onnx"),
                       {"Det.ocr_version": OCRVersion("PP-OCRv5"), "Det.model_type": ModelType("mobile"),
                        "Rec.ocr_version": OCRVersion("PP-OCRv5"), "Rec.model_type": ModelType("mobile"),
                        "Rec.lang_type": LangRec("eslav")})
    if lang == "fr":
        return Profile("ppocrv5_mobile_latin", "v5_mobile",
                       ("ch_PP-OCRv5_det_mobile.onnx", "latin_PP-OCRv5_rec_mobile.onnx"),
                       {"Det.ocr_version": OCRVersion("PP-OCRv5"), "Det.model_type": ModelType("mobile"),
                        "Rec.ocr_version": OCRVersion("PP-OCRv5"), "Rec.model_type": ModelType("mobile"),
                        "Rec.lang_type": LangRec("latin")})
    if lang == "es" or (lang == "en" and english_profile == "ppocrv6_tiny"):
        return Profile("ppocrv6_tiny", "v6",
                       ("PP-OCRv6_det_tiny.onnx", "PP-OCRv6_rec_tiny.onnx"),
                       {"Det.ocr_version": OCRVersion("PP-OCRv6"), "Det.model_type": ModelType("tiny"),
                        "Rec.ocr_version": OCRVersion("PP-OCRv6"), "Rec.model_type": ModelType("tiny"),
                        "Rec.lang_type": LangRec("ch")})
    return None


def models_root() -> Path:
    import os
    from komyst.runtime import runtime_paths

    env_val = os.environ.get("KOMYST_OCR_MODELS_DIR", "").strip()
    if env_val:
        explicit = Path(env_val).expanduser()
        return explicit / "rapidocr" if (explicit / "rapidocr").is_dir() else explicit

    canonical = runtime_paths.models_root() / "rapidocr"
    if os.environ.get("KOMYST_RUNTIME_ISOLATION_GUARD") == "1" or canonical.is_dir():
        return canonical
    try:
        eval_dir = runtime_paths.default_user_data_root() / "models_eval"
        if eval_dir.is_dir():
            return eval_dir
    except RuntimeError:
        pass
    legacy = ocr_models.models_dir() / "rapidocr"
    if legacy.is_dir():
        return legacy
    return canonical


def expected_profile_name(choice: str, english_profile: str = "") -> str:
    """Name of the dedicated profile configured for ``choice`` (even if files are absent)."""
    lang = normalize_lang(choice)
    if not lang:
        return ""
    try:
        profile = _profile(lang, english_profile)
    except ImportError:
        return ""
    return profile.name if profile is not None else ""


def profile_for(choice: str, english_profile: str = "") -> Profile | None:
    """The language's profile when its files are present, else ``None`` (bundled engine)."""
    lang = normalize_lang(choice)
    if not lang:
        return None
    try:
        profile = _profile(lang, english_profile)
    except ImportError:  # RapidOCR 3 not installed: the bundled engine reads every language
        return None
    if profile is None:
        return None
    root = models_root() / profile.folder
    return profile if all((root / name).is_file() for name in profile.files) else None


class RapidOCRProfileEngine:
    """RapidOCR 3 behind the call shape the pipeline already uses for RapidOCR 1.x:
    ``engine(image, use_cls=False)`` -> ``([[polygon, text, score], ...], elapsed)``."""

    def __init__(self, profile: Profile, *, use_dml: bool):
        from rapidocr import RapidOCR

        root = models_root() / profile.folder
        params = dict(profile.params) if profile.name != "ppocrv6_manga" else _manga_params(root)
        params["Global.model_root_dir"] = str(root)
        params["Global.use_cls"] = False  # comic lettering is never upside down
        if use_dml:
            params["EngineConfig.onnxruntime.use_dml"] = True
        self.profile = profile
        self._call_lock = threading.Lock()
        self._engine = RapidOCR(params=params)

    def __call__(self, image, use_cls=False, use_det=True, use_rec=True, **_ignored):
        started = time.perf_counter()
        with self._call_lock:
            if use_det is False:
                # Recogniser only (a crop already holding one line): RapidOCR 1.x shape
                # ``[[text, score], ...]``. RapidOCR 3's ``update_params`` mutates ``self._engine``
                # in place, so every call must pass ``use_det``/``use_cls``/``use_rec`` explicitly.
                output = self._engine(image, use_det=False, use_cls=False, use_rec=bool(use_rec))
                texts = list(getattr(output, "txts", None) or [])
                scores = list(getattr(output, "scores", None) or [1.0] * len(texts))
                results = [[str(text), float(score)] for text, score in zip(texts, scores)]
                return (results or None), time.perf_counter() - started
            output = self._engine(image, use_det=True, use_cls=False, use_rec=bool(use_rec))
        boxes = getattr(output, "boxes", None)
        texts = getattr(output, "txts", None)
        scores = getattr(output, "scores", None)
        results = []
        if boxes is not None and texts is not None:
            for box, text, score in zip(boxes, texts, scores if scores is not None else [1.0] * len(texts)):
                results.append([np.asarray(box, dtype=np.float32).tolist(), str(text), float(score)])
        return (results or None), time.perf_counter() - started
