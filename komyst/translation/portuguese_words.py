"""Words of a pt-BR translation that are not Portuguese ("ESTOVA ESPERANDO").

DeepL occasionally returns a non-word; nothing downstream noticed, because the
validators ask whether the text is Portuguese overall, not whether each word is.
The table (assets/lexicon/portuguese_freq.tsv.gz, from wordfreq, CC BY-SA 4.0)
covers ~148,000 forms. A word the source itself carries (a name, "COSSACK") or
an English word kept on purpose is never counted.
"""
from __future__ import annotations

import functools
import gzip
import re
import unicodedata

_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")
_NON_LATIN_SCRIPT_RE = re.compile(
    r"[\u0400-\u04ff\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]"
)
MIN_WORD_LENGTH = 4


@functools.lru_cache(maxsize=1)
def _portuguese_words() -> frozenset[str]:
    from komyst.runtime.paths import REPO_ROOT

    path = REPO_ROOT / "assets" / "lexicon" / "portuguese_freq.tsv.gz"
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            words = set()
            for line in handle:
                word = line.split("\t", 1)[0].strip()
                if word:
                    words.update(word.split("-"))
            # Accent-free forms too: the table spells "SAIRMOS", DeepL "SAÍRMOS".
            return frozenset(words | {_fold(word) for word in words})
    except OSError:
        return frozenset()


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(text or "").upper()) if not unicodedata.combining(c))


def unknown_target_words(translation: str, source: str = "") -> list[str]:
    """Words of ``translation`` that are neither Portuguese nor taken from ``source``."""
    vocabulary = _portuguese_words()
    if not vocabulary:
        return []
    from komyst.review.region_taxonomy import is_english_word

    source_words = {_fold(word) for word in _WORD.findall(str(source or ""))}
    # Glued source tokens ("SEOKJINKIM") still carry the name the translation splits out.
    source_letters = re.sub(r"[^A-Z]", "", _fold(source))
    non_latin_source = bool(_NON_LATIN_SCRIPT_RE.search(str(source or "")))
    target_text = str(translation or "")
    mixed_case_target = any(ch.islower() for ch in target_text)
    unknown = []
    for word in _WORD.findall(target_text):
        key = unicodedata.normalize("NFC", word.upper())
        folded = _fold(key)
        if non_latin_source and word[0].isupper() and (mixed_case_target or len(_WORD.findall(target_text)) <= 2) and not (mixed_case_target and word.isupper() and len(word) >= 4):
            # Romanized proper nouns from non-Latin scripts ("Baekpyo", "Myeongju")
            # have no Latin counterpart in the source text by construction.
            continue
        if (len(key) < MIN_WORD_LENGTH or key in vocabulary or folded in vocabulary or folded in source_words
                or folded in source_letters or is_english_word(folded)
                or _diminutive_of_known_word(folded, vocabulary)):
            continue
        if key not in unknown:
            unknown.append(key)
    return unknown


_DIMINUTIVE = re.compile(r"^(?P<stem>[A-Z]{3,}?)Z?(?:INH|IT)(?P<gender>[OA])S?$")


def _diminutive_of_known_word(folded: str, vocabulary) -> bool:
    """A regular diminutive of a known word: INSETOZINHO, CASINHA, GATINHOS, MOCITA."""
    match = _DIMINUTIVE.match(folded)
    if not match:
        return False
    stem, gender = match.group("stem"), match.group("gender")
    return any(form in vocabulary for form in (stem, stem + gender, stem + "O", stem + "A", stem + "E"))


MIN_RESTORE_SIMILARITY = 0.55


def restore_corrupted_source_words(translation: str, source: str, unknown: list[str]) -> str:
    """Put back the source word a provider turned into a non-word ("GEHENNA" -> "GEENOM").

    A translation word Portuguese does not have, that resembles a source word the translation
    dropped, is that source word mangled: the source spelling is the only safe repair. Words
    with no close source counterpart (a real invented word) are left for review, untouched.
    """
    import difflib

    present = {_fold(w) for w in _WORD.findall(str(translation or ""))}
    from komyst.review.region_taxonomy import word_zipf

    # Only a name or coinage can be "mangled back": an ordinary English word the
    # provider rendered as an unfamiliar Portuguese form (INSECT -> INSETOZINHO,
    # DISTRACTED -> DISTRATADO) was translated, and restoring it puts English back.
    candidates = [w for w in _WORD.findall(str(source or ""))
                  if len(w) >= MIN_WORD_LENGTH and _fold(w) not in present
                  and word_zipf(_fold(w)) < 3.0]
    repaired = str(translation or "")
    for bad in unknown:
        best, best_ratio = "", MIN_RESTORE_SIMILARITY
        for word in candidates:
            if _fold(word)[:1] != _fold(bad)[:1]:
                continue
            ratio = difflib.SequenceMatcher(None, _fold(word), _fold(bad)).ratio()
            if ratio >= best_ratio:
                best, best_ratio = word, ratio
        if best:
            repaired = re.sub(rf"\b{re.escape(bad)}\b", best.upper(), repaired, flags=re.IGNORECASE)
            candidates.remove(best)
    return repaired


_MALE_PRONOUNS = re.compile(r"\b(?:HE|HIS|HIM|HIMSELF)\b")
_FEMALE_PRONOUNS = re.compile(r"\b(?:SHE|HER|HERS|HERSELF)\b")
# Portuguese contractions of the article before a name, masculine <-> feminine.
_ARTICLE_SWAP = {"O": "A", "DO": "DA", "NO": "NA", "PELO": "PELA", "AO": "À"}


def chapter_name_genders(sources, names):
    """Grammatical gender of each name, from the English pronouns the chapter uses with it.

    Only lines that mention exactly one of the names count, and only subject/possessive
    pronouns (an object "her"/"him" usually points at someone else); a name is gendered
    when its pronouns agree and never disagree. Nothing is assumed from the
    name's spelling (Portuguese guesses "a Asta" from the final -a).
    """
    upper_names = sorted({str(name).upper() for name in names or () if len(str(name)) >= 3})
    counts = {name: [0, 0] for name in upper_names}
    for source in sources or ():
        text = str(source or "").upper()
        present = [name for name in upper_names if re.search(rf"\b{re.escape(name)}\b", text)]
        if len(present) != 1:
            continue
        counts[present[0]][0] += len(_MALE_PRONOUNS.findall(text))
        counts[present[0]][1] += len(_FEMALE_PRONOUNS.findall(text))
    genders = {}
    for name, (male, female) in counts.items():
        if male and not female:
            genders[name] = "m"
        elif female and not male:
            genders[name] = "f"
    return genders


def chapter_name_candidates(sources, minimum=2):
    """Rare words (Zipf < 3) the chapter repeats: the names it writes ("ASTA", "HAGE")."""
    from komyst.review import region_taxonomy

    seen = {}
    for source in sources or ():
        for token in set(re.findall(r"[A-Za-z]{3,}", str(source or "").upper())):
            if region_taxonomy.word_zipf(token) < 3.0:
                seen[token] = seen.get(token, 0) + 1
    return [token for token, count in seen.items() if count >= minimum]


def align_name_articles(target, genders):
    """The article/contraction right before a gendered name made to agree with it."""
    text = str(target or "")
    for name, gender in genders.items():
        wanted = _ARTICLE_SWAP if gender == "f" else {v: k for k, v in _ARTICLE_SWAP.items()}

        def swap(match):
            article = match.group(1)
            replacement = wanted.get(article.upper())
            if replacement is None:
                return match.group(0)
            if article.islower():
                replacement = replacement.lower()
            elif article[0].isupper() and not article.isupper():
                replacement = replacement.capitalize()
            return f"{replacement}{match.group(2)}"

        keys = "|".join(re.escape(k) for k in sorted(wanted, key=len, reverse=True))
        text = re.sub(rf"\b({keys})(\s+{re.escape(name)}\b)", swap, text, flags=re.IGNORECASE)
    return text
