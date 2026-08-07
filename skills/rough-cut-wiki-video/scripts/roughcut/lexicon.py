"""Post-recognition term repair against a user-supplied glossary.

Hotwords cannot carry a real glossary: faster-whisper truncates them at
``max_length // 2 - 1`` (223) tokens, which silently drops everything past the
first few entries. Repairing the transcript afterwards has no such ceiling, so
an arbitrarily large glossary stays usable at negligible cost and without
biasing the decoder.

Two bands exist, because character similarity and pronunciation similarity fail
in opposite ways:

``repair`` is the automatic band. It only rewrites spans that are already close
character-for-character, which is safe enough to apply unattended.

``propose`` is the reviewed band, and it adds pronunciation comparison. Whisper's
Chinese mistakes are overwhelmingly homophones, which character distance cannot
see at all: on real footage 抵扣布丁 for 底壳固定 scores 0.00 by characters and
0.76 by pinyin. Pronunciation alone cannot be trusted either, since the opposites
热端风扇/冷端风扇 reach 0.87 and the wrong-but-plausible 紧抵扣/进气口 reaches
0.88 — higher than the correct repair. No threshold separates them, so proposals
are never applied automatically; they are handed to an agent that can weigh them
against the procedure text.
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


def repair(text: str | None, terms: list[str]) -> tuple[str | None, list[dict]]:
    """Replace misheard spans with glossary terms; never insert or delete text."""
    if not text or not terms:
        return text, []
    taken: list[tuple[int, int]] = []
    applied: list[dict] = []
    for score, start, end, found, term in _candidates(text, terms):
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
