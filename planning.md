# Provenance Guard — Planning Spec

Written before implementation. Updated only if stretch features are added.

## Problem Statement

Creative platforms need a backend service that classifies whether submitted text is likely human-written or AI-generated, communicates uncertainty honestly, and gives creators a path to appeal misclassification. False positives (labeling human work as AI) are worse than false negatives on a writing platform.

---

## Detection Signals

### Signal 1: LLM Semantic Assessment (Groq / llama-3.3-70b-versatile)

**What it measures:** Holistic semantic and stylistic coherence — whether the text reads like typical LLM output (formulaic transitions, balanced hedging, generic phrasing).

**Output:** Float `0.0–1.0` where **1.0 = very likely AI-generated**.

**Why it differs:** LLMs produce semantically smooth, structurally balanced prose. Humans often have idiosyncratic voice, tangents, and uneven polish.

**Blind spots:** Heavily edited human formal writing; non-native speakers who write in a stiff, template-like style; human writers mimicking "AI voice" ironically.

### Signal 2: Stylometric Heuristics (Pure Python)

**What it measures:** Structural statistical properties:
- Sentence length variance (AI tends toward uniform sentence lengths)
- Type-token ratio / vocabulary diversity (AI often uses a narrower, "safe" vocabulary band)
- Punctuation density and contraction rate (casual human markers)

**Output:** Float `0.0–1.0` where **1.0 = structural patterns typical of AI text**.

**Why it differs:** Human casual writing has high variance, contractions, and irregular rhythm. AI text clusters around median sentence length and moderate vocabulary diversity.

**Blind spots:** Formal academic prose (low variance, no contractions); poetry with repetition; very short submissions (insufficient data for stats).

### Signal 3: Rhetorical Pattern Analysis (Pure Python) — Stretch

**What it measures:** AI-typical discourse markers, hedging phrases, generic vocabulary ("stakeholders", "leverage"), and list-of-three rhetorical structures.

**Output:** Float `0.0–1.0` where **1.0 = rhetorical patterns typical of AI text**.

**Why it differs:** LLMs overuse formulaic transitions and balanced triplet constructions. Casual human writing rarely stacks multiple discourse markers per paragraph.

**Blind spots:** Deliberately formal human essays; legal/business writing that naturally uses similar vocabulary; satire mimicking AI voice.

### Combining Signals (Ensemble — 3 signals)

```
raw_score = 0.45 × llm_score + 0.30 × stylo_score + 0.25 × rhetoric_score
```

If signal spread (max − min) exceeds 0.25, pull the combined score toward 0.5 (uncertainty zone).

**High-confidence AI gate:** Score ≥ 0.75 only if **at least 2 of 3** individual signals ≥ 0.60. Otherwise cap at 0.74 (uncertain band).

---

## Stretch Features

### Ensemble Detection (implemented)

Added **Signal 3: Rhetorical Pattern Analysis** — measures density of AI discourse markers ("Furthermore", "It is important to note"), hedging phrases, generic corporate vocabulary, and list-of-three sentence structures.

**Why a third signal:** LLM captures holistic semantics; stylometrics capture structure; rhetoric captures *discourse habits* — a property neither other signal measures directly.

**Weighting rationale:** LLM remains highest weight (0.45) because it generalizes best; stylometrics (0.30) and rhetoric (0.25) corroborate without overpowering semantic judgment.

**Agreement rule:** With 3 signals, high-confidence AI requires majority agreement (2/3 ≥ 0.60) instead of requiring all signals — reduces false negatives on obvious AI text while still blocking single-signal false positives.

---

## Uncertainty Representation

| Score range | Attribution | Label variant |
|-------------|-------------|---------------|
| ≥ 0.75 | `likely_ai` | High-confidence AI |
| 0.36 – 0.74 | `uncertain` | Uncertain |
| ≤ 0.35 | `likely_human` | High-confidence human |

**What 0.6 means:** The system leans slightly toward AI but is **not confident enough to label it as such**. Users see the "Uncertain" label, not "Likely AI."

**Calibration:** Tested with 4 reference texts (clearly AI, clearly human, formal human, lightly edited AI). Scores should span the full range with borderline cases landing in 0.36–0.74.

---

## Transparency Label Design

### High-confidence AI (score ≥ 0.75)

> **Likely AI-generated** — Our analysis suggests this content was probably created with AI tools (confidence: {pct}%). If you believe this is incorrect, the author can submit an appeal for human review.

### High-confidence human (score ≤ 0.35)

> **Likely human-written** — Our analysis found patterns consistent with original human authorship (confidence: {pct}%). Attribution is never guaranteed; this is one signal among many.

### Uncertain (score 0.36–0.74)

> **Uncertain attribution** — We couldn't determine authorship with confidence ({pct}% leaning toward AI). This content may be human-written, AI-assisted, or AI-generated. If you're the creator and this label is wrong, you can submit an appeal.

---

## Appeals Workflow

**Who:** The original `creator_id` associated with a submission (validated on appeal).

**Input:** `content_id`, `creator_reasoning` (free text explaining why the classification is wrong).

**System actions:**
1. Verify content exists and is in `classified` status
2. Update status → `under_review`
3. Append audit log entry with `event_type: "appeal"`, original scores, and creator reasoning
4. Return confirmation with updated status

**Reviewer view:** GET `/log` shows the original classification entry plus the appeal entry with reasoning, both signal scores, and timestamp — enough to manually re-evaluate.

**Not in scope:** Automated re-classification.

---

## Anticipated Edge Cases

1. **Formal academic prose** — Low sentence-length variance and no contractions may push stylometrics toward AI even when human-written. Mitigation: disagreement pull + uncertain band + appeals.

2. **Very short text (< 50 words)** — Insufficient tokens for reliable stylometrics. Mitigation: stylometric signal defaults toward 0.5 (neutral); label likely lands in uncertain.

3. **Non-native English writers** — May produce stiff, uniform sentences resembling AI. Mitigation: LLM may also flag; appeals workflow is the safety net.

4. **Heavily AI-edited human drafts** — Hybrid content may score mid-range (correct behavior — uncertain label).

---

## Architecture

### Narrative

A creator submits text via `POST /submit`. The API validates input, runs Signal 1 (LLM) and Signal 2 (stylometrics) in sequence, combines scores with disagreement-aware weighting, maps the result to an attribution label and transparency text, persists everything to SQLite, writes a structured audit log entry, and returns the full response. If a creator disagrees, they call `POST /appeal` with their reasoning; the system updates status to `under_review` and logs the appeal alongside the original decision.

### Diagram

```
SUBMISSION FLOW
===============

  Client                Flask API              Detection           Scoring & Labels        Storage
    |                      |                       |                      |                  |
    |  POST /submit        |                       |                      |                  |
    |  {text, creator_id}  |                       |                      |                  |
    |--------------------->|                       |                      |                  |
    |                      |  raw text             |                      |                  |
    |                      |---------------------->| Signal 1 (LLM)       |                  |
    |                      |                       |---- llm_score ------>|                  |
    |                      |  raw text             |                      |                  |
    |                      |---------------------->| Signal 2 (Stylo)     |                  |
    |                      |                       |---- stylo_score ---->|                  |
    |                      |                       |                      | combine scores   |
    |                      |                       |                      | map to label     |
    |                      |                       |                      |----------------->|
    |                      |                       |                      |  audit log entry |
    |  {content_id,        |                       |                      |                  |
    |   attribution,       |<----------------------|----------------------|<-----------------|
    |   confidence, label} |                       |                      |                  |
    |<---------------------|                       |                      |                  |


APPEAL FLOW
===========

  Client                Flask API                                    Storage
    |                      |                                            |
    |  POST /appeal        |                                            |
    |  {content_id,        |                                            |
    |   creator_reasoning} |                                            |
    |--------------------->|                                            |
    |                      |  lookup original classification            |
    |                      |------------------------------------------->|
    |                      |  update status → "under_review"            |
    |                      |  append appeal audit entry                 |
    |                      |------------------------------------------->|
    |  {status, message}   |                                            |
    |<---------------------|                                            |
```

---

## API Surface

| Method | Path | Body | Returns |
|--------|------|------|---------|
| POST | `/submit` | `{text, creator_id}` | `{content_id, attribution, confidence, label, llm_score, stylo_score, status}` |
| POST | `/appeal` | `{content_id, creator_reasoning}` | `{content_id, status, message}` |
| GET | `/log` | — | `{entries: [...]}` (most recent 50) |
| GET | `/health` | — | `{status: "ok"}` |

---

## AI Tool Plan

### M3 — Submission endpoint + Signal 1

**Spec sections provided:** Detection Signals (Signal 1), Architecture diagram, API Surface.

**Ask AI to generate:** Flask app skeleton, `POST /submit` stub, `signals/llm_signal.py`, SQLite audit log init, `GET /log`.

**Verify:** curl POST returns `content_id`; log entry appears; signal function tested standalone with 2–3 texts.

### M4 — Signal 2 + Confidence Scoring

**Spec sections provided:** Detection Signals (Signal 2), Uncertainty Representation, Architecture diagram.

**Ask AI to generate:** `signals/stylometric.py`, `scoring.py` with combine logic matching thresholds.

**Verify:** 4 test inputs produce meaningfully different scores; audit log records both signal scores.

### M5 — Production Layer

**Spec sections provided:** Transparency Label Design, Appeals Workflow, Architecture diagram.

**Ask AI to generate:** `labels.py`, `POST /appeal`, Flask-Limiter on `/submit`.

**Verify:** All 3 label variants reachable; appeal updates status and log; rate limit returns 429 after 10 rapid requests.
