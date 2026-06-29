"""Signal 2: Stylometric heuristics — pure Python structural analysis."""

import math
import re
import statistics


def _sentence_lengths(text: str) -> list[int]:
    sentences = re.split(r"[.!?]+", text)
    return [len(s.split()) for s in sentences if s.strip()]


def _type_token_ratio(text: str) -> float:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 5:
        return 0.5
    return len(set(words)) / len(words)


def _contraction_rate(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    contractions = len(re.findall(r"\b\w+'\w+\b", text))
    return contractions / len(words)


def _punctuation_density(text: str) -> float:
    if not text:
        return 0.0
    punct = len(re.findall(r"[,;:—\-()\"']", text))
    return punct / len(text)


def analyze_stylometric(text: str) -> float:
    """
    Return probability (0–1) that text structurally resembles AI output.

    AI text tends toward: uniform sentence lengths, moderate vocabulary diversity,
    low contraction rate, moderate punctuation density.
    """
    word_count = len(text.split())
    if word_count < 15:
        return 0.5

    lengths = _sentence_lengths(text)
    if len(lengths) < 2:
        return 0.5

    length_variance = statistics.variance(lengths) if len(lengths) > 1 else 0.0
    ttr = _type_token_ratio(text)
    contraction = _contraction_rate(text)
    punct = _punctuation_density(text)

    # Low variance → more AI-like (uniform sentences)
    variance_score = 1.0 - min(1.0, length_variance / 80.0)

    # TTR in 0.45–0.65 band is typical of AI; very high or very low differs
    if 0.4 <= ttr <= 0.65:
        ttr_score = 0.7
    elif ttr > 0.75:
        ttr_score = 0.2
    else:
        ttr_score = 0.5

    # Few contractions → more formal/AI-like
    contraction_score = 1.0 - min(1.0, contraction * 20)

    # Moderate punctuation density (not too sparse, not chaotic)
    if 0.02 <= punct <= 0.06:
        punct_score = 0.65
    elif punct > 0.08:
        punct_score = 0.25
    else:
        punct_score = 0.5

    combined = (
        0.35 * variance_score
        + 0.30 * ttr_score
        + 0.20 * contraction_score
        + 0.15 * punct_score
    )
    return round(max(0.0, min(1.0, combined)), 2)
