"""Post-recognition term repair, driven mainly by the procedure's own wording.

Hotwords cannot carry a real glossary: faster-whisper truncates them at
``max_length // 2 - 1`` (223) tokens, which silently drops everything past the
first few entries. Repairing the transcript afterwards has no such ceiling, so
an arbitrarily large glossary stays usable at negligible cost and without
biasing the decoder.

Two bands exist, because character similarity and pronunciation similarity fail
in opposite ways:

``repair`` is the automatic band. It only rewrites spans that are already close
character-for-character, and it never touches a span overlapping a term the text
already spells correctly. That guard is what makes the band safe to apply
unattended: without it, a real 530-term glossary containing 77 pairs of
near-identical terms rewrote 更换冷端风扇 into its opposite 更换热端风扇, slid a
window across correct text to produce 检主热端风扇, and — once the procedure was
added as vocabulary — flipped 安装底壳固定螺丝 to 移除底壳固定螺丝, which would
have sent the take to the wrong step.

``propose`` is the reviewed band, and it adds pronunciation comparison. Whisper's
Chinese mistakes are overwhelmingly homophones, which character distance cannot
see at all: on real footage 抵扣布丁 for 底壳固定 scores 0.00 by characters and
0.76 by pinyin. Pronunciation alone cannot be trusted either, since the opposites
热端风扇/冷端风扇 reach 0.87 and the wrong-but-plausible 紧抵扣/进气口 reaches
0.88 — higher than the correct repair. No threshold separates them, so proposals
are never applied automatically; they are handed to an agent that can weigh them
against the procedure text. This band stays deliberately permissive, anchor guard
included, because a reviewer can reject a bad suggestion but cannot recover one
that was never offered.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

# Below this length a fuzzy hit is more likely to be coincidence than a typo.
MIN_TERM_LENGTH = 3
# Three-character terms need near-certainty; they collide far too easily.
SHORT_TERM_LENGTH = 3
SHORT_TERM_THRESHOLD = 0.85
DEFAULT_THRESHOLD = 0.75
# Floors for the reviewed band. Either channel may qualify a span, because a
# homophone scores near zero on characters and a typo scores low on pinyin.
PROPOSE_CHAR_THRESHOLD = 0.60
PROPOSE_PINYIN_THRESHOLD = 0.70
# The automatic band additionally requires the characters it would change to be
# plausibly misheard. Separating 山/扇 (shan/shan) from 冷/热 (leng/re) is what
# distinguishes a real mishearing from a different word that merely looks close.
# Measured on a 530-term glossary: this rejects all 77 pairs of distinct valid
# terms that character similarity alone would have let through, while keeping the
# homophone substitutions that are genuine mishearings.
AUTO_SOUND_THRESHOLD = 0.7
_CJK = re.compile(r"[\u4e00-\u9fff]")


def load_terms(path: Path | None) -> list[str]:
    """Read one term per line; missing files simply disable repair."""
    if not path:
        return []
    file = Path(path)
    if not file.is_file():
        return []
    seen: dict[str, None] = {}
    for raw in file.read_text(encoding="utf-8-sig").splitlines():
        term = raw.strip()
        if len(term) >= MIN_TERM_LENGTH and _CJK.search(term):
            seen.setdefault(term, None)
    return list(seen)


def _threshold_for(term: str) -> float:
    return SHORT_TERM_THRESHOLD if len(term) <= SHORT_TERM_LENGTH else DEFAULT_THRESHOLD


def pinyin_available() -> bool:
    """Pronunciation comparison is optional; without it only characters are used."""
    try:
        import pypinyin  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=4096)
def _syllables(text: str) -> tuple[str, ...]:
    """One syllable per character, so a window's pinyin is a cheap slice-join."""
    from pypinyin import Style, lazy_pinyin

    return tuple(lazy_pinyin(text, style=Style.NORMAL, errors=lambda item: list(item)))


def _sound(text: str) -> str:
    return "".join(_syllables(text))


def _candidates(text: str, terms: list[str]) -> list[tuple[float, int, int, str, str]]:
    """Collect (score, start, end, found, term) for windows that look misheard."""
    hits: list[tuple[float, int, int, str, str]] = []
    length = len(text)
    for term in terms:
        if term in text:
            continue
        minimum = _threshold_for(term)
        size = len(term)
        best_for_term: tuple[float, int, int, str, str] | None = None
        for window in {size - 1, size, size + 1}:
            if window < MIN_TERM_LENGTH or window > length:
                continue
            for start in range(length - window + 1):
                found = text[start:start + window]
                if not _CJK.search(found):
                    continue
                score = SequenceMatcher(None, found, term).ratio()
                if score < minimum:
                    continue
                # Length-adjusted rank: a shorter partial window can score higher than
                # the full misheard span (热端风 vs 热端风山), so prefer closeness to
                # the glossary term length before raw ratio.
                aligned = sum(a == b for a, b in zip(found, term))
                candidate = (score, start, start + window, found, term, aligned)
                if best_for_term is None:
                    best_for_term = candidate
                    continue
                old_score, old_start, old_end, _, _, old_aligned = best_for_term
                old_delta = abs((old_end - old_start) - size)
                new_delta = abs(window - size)
                # Prefer length-close windows, then ratio, then same-index char overlap
                # so "热端风山" beats the equal-ratio shifted window "装热端风".
                if (new_delta, -score, -aligned, start) < (old_delta, -old_score, -old_aligned, old_start):
                    best_for_term = candidate
        if best_for_term is not None:
            hits.append(best_for_term[:5])
    hits.sort(
        key=lambda hit: (
            abs((hit[2] - hit[1]) - len(hit[4])),
            -hit[0],
            -sum(a == b for a, b in zip(hit[3], hit[4])),
            hit[1],
        )
    )
    return hits


def _sound_plausible(found: str, term: str, threshold: float = AUTO_SOUND_THRESHOLD) -> bool:
    """Could a speaker saying ``term`` be transcribed as ``found``?

    Only the characters that differ are compared, because the shared ones carry no
    information about the substitution. On equal-length spans this is decisive:
    the genuine 山 for 扇 are the same syllable, while the opposites 冷 and 热 share
    nothing, even though both differ from their term by exactly one character and so
    score identically at 0.75 on characters.
    """
    if len(found) == len(term):
        changed = [(a, b) for a, b in zip(found, term) if a != b]
        return all(
            SequenceMatcher(None, _sound(a), _sound(b)).ratio() >= threshold
            for a, b in changed
        )
    # Differing lengths shift the alignment, so compare the spans as a whole.
    return SequenceMatcher(None, _sound(found), _sound(term)).ratio() >= threshold


def _anchored_spans(text: str, terms: list[str]) -> list[tuple[int, int]]:
    """Spans the text already spells as a known term, which must be left alone.

    Every observed false repair overlapped one of these: the vocabulary's own
    near-neighbours are similar enough to pass any character threshold, so
    correctly transcribed text was the most likely thing to be rewritten.
    """
    spans: list[tuple[int, int]] = []
    for term in terms:
        if len(term) < MIN_TERM_LENGTH:
            continue
        start = text.find(term)
        while start >= 0:
            spans.append((start, start + len(term)))
            start = text.find(term, start + 1)
    return spans


def repair(text: str | None, terms: list[str]) -> tuple[str | None, list[dict]]:
    """Replace misheard spans with known terms; never insert or delete text."""
    if not text or not terms:
        return text, []
    if not pinyin_available():
        # Character similarity alone cannot tell 冷端风扇 from 热端风扇, so without
        # pronunciation checking nothing here is safe to apply unattended. Suggestions
        # still reach the reviewed band, which is where a human can judge them.
        return text, []
    anchors = _anchored_spans(text, terms)
    taken: list[tuple[int, int]] = []
    applied: list[dict] = []
    for score, start, end, found, term in _candidates(text, terms):
        if any(start < stop and begin < end for begin, stop in anchors):
            continue
        if not _sound_plausible(found, term):
            continue
        if any(start < stop and begin < end for begin, stop in taken):
            continue
        taken.append((start, end))
        applied.append({"found": found, "corrected": term, "score": round(score, 3)})
    if not applied:
        return text, []
    for (start, end), change in sorted(zip(taken, applied), key=lambda pair: -pair[0][0]):
        text = text[:start] + change["corrected"] + text[end:]
    return text, applied


def propose(text: str | None, terms: list[str], *, use_pinyin: bool = True) -> list[dict]:
    """Suggest repairs for review; the caller decides whether to apply them.

    Returns one suggestion per glossary term at most, each identified by the exact
    substring it would replace so the caller can apply it with a plain string
    replacement and stay immune to offset drift.
    """
    if not text or not terms:
        return []
    sound = use_pinyin and pinyin_available()
    per_char = _syllables(text) if sound else ()
    suggestions: list[dict] = []
    for term in terms:
        if term in text:
            continue
        size = len(term)
        term_sound = _sound(term) if sound else ""
        best: tuple[float, float, float, str] | None = None
        for window in {size - 1, size, size + 1}:
            if window < MIN_TERM_LENGTH or window > len(text):
                continue
            for start in range(len(text) - window + 1):
                found = text[start:start + window]
                if not _CJK.search(found) or found == term:
                    continue
                char = SequenceMatcher(None, found, term).ratio()
                heard = (
                    SequenceMatcher(None, "".join(per_char[start:start + window]), term_sound).ratio()
                    if sound else 0.0
                )
                if char < PROPOSE_CHAR_THRESHOLD and heard < PROPOSE_PINYIN_THRESHOLD:
                    continue
                rank = max(char, heard)
                if best is None or rank > best[0]:
                    best = (rank, char, heard, found)
        # Anything the automatic band would already handle is not worth reviewing.
        if best is None or best[1] >= _threshold_for(term):
            continue
        rank, char, heard, found = best
        suggestions.append({
            "found": found,
            "suggested": term,
            "char_score": round(char, 3),
            "pinyin_score": round(heard, 3),
            "rank": round(rank, 3),
        })
    suggestions.sort(key=lambda item: -item["rank"])
    return suggestions
