"""Transparency label generation."""

from scoring import AI_THRESHOLD, HUMAN_THRESHOLD


def generate_label(confidence: float, attribution: str) -> str:
    pct = int(round(confidence * 100))

    if attribution == "likely_ai":
        return (
            f"Likely AI-generated — Our analysis suggests this content was probably "
            f"created with AI tools (confidence: {pct}%). If you believe this is incorrect, "
            f"the author can submit an appeal for human review."
        )

    if attribution == "likely_human":
        human_pct = int(round((1 - confidence) * 100))
        return (
            f"Likely human-written — Our analysis found patterns consistent with original "
            f"human authorship (confidence: {human_pct}%). Attribution is never guaranteed; "
            f"this is one signal among many."
        )

    return (
        f"Uncertain attribution — We couldn't determine authorship with confidence "
        f"({pct}% leaning toward AI). This content may be human-written, AI-assisted, "
        f"or AI-generated. If you're the creator and this label is wrong, you can submit an appeal."
    )


def label_variant_name(confidence: float) -> str:
    if confidence >= AI_THRESHOLD:
        return "high_confidence_ai"
    if confidence <= HUMAN_THRESHOLD:
        return "high_confidence_human"
    return "uncertain"
