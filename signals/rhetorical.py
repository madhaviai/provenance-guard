"""Signal 3: Rhetorical pattern analysis — AI discourse marker density."""

import re

AI_TRANSITIONS = (
    "furthermore",
    "moreover",
    "in addition",
    "in conclusion",
    "it is important to note",
    "it is worth noting",
    "it is equally essential",
    "on the other hand",
    "that being said",
    "in today's world",
    "in today's society",
    "plays a crucial role",
    "plays a vital role",
    "a wide range of",
    "delve into",
    "navigate the complexities",
    "at its core",
    "in summary",
    "to summarize",
    "as a result",
    "consequently",
)

HEDGING_PATTERNS = (
    "it is important",
    "it is essential",
    "it is worth",
    "may be",
    "might be",
    "could be",
    "generally speaking",
    "in many cases",
    "to some extent",
    "arguably",
    "often considered",
)

GENERIC_NOUNS = (
    "stakeholders",
    "paradigm",
    "landscape",
    "framework",
    "implementation",
    "utilize",
    "leverage",
    "robust",
    "comprehensive",
    "multifaceted",
    "transformative",
)


def _count_phrase_hits(text: str, phrases: tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(1 for p in phrases if p in lower)


def _list_of_three_score(text: str) -> float:
    """Detect 'A, B, and C' / 'A, B, or C' triplet patterns common in AI prose."""
    triplets = re.findall(
        r"\b\w[\w'-]*,\s+\w[\w'-]*,\s+(?:and|or)\s+\w[\w'-]*",
        text,
        flags=re.IGNORECASE,
    )
    sentences = max(1, len(re.split(r"[.!?]+", text)))
    rate = len(triplets) / sentences
    return min(1.0, rate * 0.8)


def analyze_rhetorical(text: str) -> float:
    """
    Return probability (0–1) that text uses AI-typical rhetorical patterns.

    Measures discourse-marker density, hedging phrases, and list-of-three
    structures — properties distinct from sentence-level stylometrics or
    holistic LLM judgment.
    """
    words = text.split()
    word_count = len(words)
    if word_count < 10:
        return 0.5

    per_100 = 100.0 / word_count
    transition_hits = _count_phrase_hits(text, AI_TRANSITIONS)
    hedging_hits = _count_phrase_hits(text, HEDGING_PATTERNS)
    generic_hits = _count_phrase_hits(text, GENERIC_NOUNS)

    transition_score = min(1.0, transition_hits * per_100 * 2.5)
    hedging_score = min(1.0, hedging_hits * per_100 * 3.0)
    generic_score = min(1.0, generic_hits * per_100 * 2.0)
    triplet_score = _list_of_three_score(text)

    combined = (
        0.35 * transition_score
        + 0.25 * hedging_score
        + 0.20 * generic_score
        + 0.20 * triplet_score
    )
    return round(max(0.0, min(1.0, combined)), 2)
