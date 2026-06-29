"""Combine detection signals into a calibrated confidence score (3-signal ensemble)."""

# Ensemble weights — LLM carries most weight; structural + rhetorical support it
LLM_WEIGHT = 0.45
STYLO_WEIGHT = 0.30
RHETORIC_WEIGHT = 0.25

AI_THRESHOLD = 0.75
HUMAN_THRESHOLD = 0.35
DISAGREEMENT_THRESHOLD = 0.25
SIGNAL_AGREEMENT_MIN = 0.60
MIN_AGREEING_FOR_HIGH_AI = 2  # at least 2 of 3 signals must agree


def combine_scores(
    llm_score: float,
    stylo_score: float,
    rhetoric_score: float,
) -> float:
    """
    Merge three signals into a single AI-likelihood score (0–1).

    Weighted ensemble with disagreement pull and majority-agreement gate
    for high-confidence AI labels (false-positive protection).
    """
    scores = [llm_score, stylo_score, rhetoric_score]
    raw = (
        LLM_WEIGHT * llm_score
        + STYLO_WEIGHT * stylo_score
        + RHETORIC_WEIGHT * rhetoric_score
    )

    spread = max(scores) - min(scores)
    if spread > DISAGREEMENT_THRESHOLD:
        pull = spread * 0.35
        raw = raw * (1 - pull) + 0.5 * pull

    agreeing = sum(1 for s in scores if s >= SIGNAL_AGREEMENT_MIN)
    if raw >= AI_THRESHOLD and agreeing < MIN_AGREEING_FOR_HIGH_AI:
        raw = min(raw, AI_THRESHOLD - 0.01)

    return round(max(0.0, min(1.0, raw)), 2)


def score_to_attribution(confidence: float) -> str:
    if confidence >= AI_THRESHOLD:
        return "likely_ai"
    if confidence <= HUMAN_THRESHOLD:
        return "likely_human"
    return "uncertain"
