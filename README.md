# Provenance Guard

A backend API that creative platforms plug into to classify whether submitted text is likely human-written or AI-generated, score confidence honestly, surface transparency labels, and handle creator appeals.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
pip install -r requirements.txt
cp .env.example .env               # add your GROQ_API_KEY
python app.py                      # http://localhost:5000
```

Seed sample audit log entries:

```bash
python seed_samples.py
```

---

## Architecture Overview

When a creator submits text, the request flows through these components:

1. **Flask API** (`POST /submit`) — validates input, applies rate limiting
2. **Signal 1: LLM assessment** (Groq) — semantic/style analysis → `llm_score`
3. **Signal 2: Stylometric heuristics** — sentence variance, vocabulary diversity, contractions → `stylo_score`
4. **Signal 3: Rhetorical patterns** — AI discourse markers, hedging, list-of-three structures → `rhetoric_score`
5. **Ensemble confidence scorer** — weighted combination with disagreement pull + majority agreement gate
6. **Label generator** — maps score to plain-language transparency text
7. **SQLite storage + audit log** — persists decision with all three signal scores
8. **Response** — returns `content_id`, attribution, confidence, and label

If a creator disputes the result, `POST /appeal` updates status to `under_review` and appends an appeal entry to the audit log alongside the original classification.

See `planning.md` for the full architecture diagram.

---

## Detection Signals

### Signal 1: LLM Semantic Assessment (Groq / llama-3.3-70b-versatile)

**Measures:** Whether text reads like typical LLM output — formulaic transitions, balanced hedging, generic phrasing.

**Why chosen:** Captures semantic coherence holistically; catches polished AI prose that passes simple heuristics.

**Blind spots:** Formal human writers, non-native English, intentionally stiff prose.

### Signal 2: Stylometric Heuristics (Pure Python)

**Measures:** Sentence length variance, type-token ratio (vocabulary diversity), contraction rate, punctuation density.

**Why chosen:** Independent of semantics — AI text tends toward uniform sentence lengths and moderate vocabulary bands. Complements the LLM signal.

**Blind spots:** Academic prose, poetry with repetition, very short submissions (< 15 words).

### Signal 3: Rhetorical Pattern Analysis (Pure Python)

**Measures:** Density of AI discourse markers ("Furthermore", "It is important to note"), hedging phrases, generic corporate vocabulary, and list-of-three rhetorical structures.

**Why chosen:** Captures *discourse habits* — distinct from sentence-level stylometrics and holistic LLM judgment. AI text stacks formulaic transitions; casual human writing rarely does.

**Blind spots:** Formal business/legal writing; satire mimicking AI voice.

---

## Confidence Scoring

**Ensemble formula:** `raw = 0.45 × llm + 0.30 × stylo + 0.25 × rhetoric`

**Uncertainty pull:** If signal spread (max − min) > 0.25, score moves toward 0.5.

**False-positive protection:** High-confidence AI (≥ 0.75) requires **at least 2 of 3** signals ≥ 0.60. Single-signal spikes cap at 0.74 (Uncertain).

| Score | Attribution | Label |
|-------|-------------|-------|
| ≥ 0.75 | `likely_ai` | High-confidence AI |
| 0.36 – 0.74 | `uncertain` | Uncertain |
| ≤ 0.35 | `likely_human` | High-confidence human |

### Example Submissions (actual scores)

**High-confidence AI** (uniform, formulaic prose):

```
Text: "It is important to note that artificial intelligence plays a crucial role..."
→ llm: 1.0, stylo: 0.65, rhetoric: 0.72, confidence: 0.81, attribution: likely_ai
```

**High-confidence human** (casual, irregular voice):

```
Text: "ok so i finally tried that new ramen place downtown and honestly? underwhelming..."
→ llm: 0.33, stylo: 0.37, rhetoric: 0.12, confidence: 0.30, attribution: likely_human
```

**Uncertain** (formal academic — signals partially disagree):

```
Text: "The relationship between monetary policy and asset price inflation has been extensively studied..."
→ llm: 0.45, stylo: 0.42, rhetoric: 0.28, confidence: 0.41, attribution: uncertain
```

---

## Transparency Labels

Exact text displayed for each variant:

| Variant | Exact label text |
|---------|-----------------|
| **High-confidence AI** | "Likely AI-generated — Our analysis suggests this content was probably created with AI tools (confidence: {pct}%). If you believe this is incorrect, the author can submit an appeal for human review." |
| **High-confidence human** | "Likely human-written — Our analysis found patterns consistent with original human authorship (confidence: {pct}%). Attribution is never guaranteed; this is one signal among many." |
| **Uncertain** | "Uncertain attribution — We couldn't determine authorship with confidence ({pct}% leaning toward AI). This content may be human-written, AI-assisted, or AI-generated. If you're the creator and this label is wrong, you can submit an appeal." |

---

## Rate Limiting

**Limits:** `10 per minute; 100 per day` on `POST /submit` (per IP via Flask-Limiter).

**Reasoning:**
- A typical writer submits a few drafts per session, not dozens per minute
- 10/minute allows rapid iteration during editing while blocking scripted floods
- 100/day covers heavy legitimate use (~20 submissions over 5 sessions) while capping abuse

**Evidence** (12 rapid requests — first 10 succeed, then 429):

```
200
200
200
200
200
200
200
200
200
200
429
429
```

---

## Audit Log

Every classification and appeal is stored in SQLite. Retrieve via `GET /log`.

**Sample entries** (from `python seed_samples.py`):

```json
{
  "entries": [
    {
      "content_id": "630712f9-db10-4744-8324-e1ecccad15b6",
      "creator_id": "demo-borderline-sample",
      "event_type": "appeal",
      "timestamp": "2026-06-28T05:49:57.402386+00:00",
      "status": "under_review",
      "appeal_reasoning": "I wrote this myself for an economics seminar...",
      "original_attribution": "uncertain",
      "original_confidence": 0.44,
      "llm_score": 0.45,
      "stylo_score": 0.42
    },
    {
      "content_id": "630712f9-db10-4744-8324-e1ecccad15b6",
      "event_type": "classification",
      "attribution": "uncertain",
      "confidence": 0.44,
      "llm_score": 0.45,
      "stylo_score": 0.42,
      "status": "classified"
    },
    {
      "content_id": "5f54999f-1023-485a-9f8f-0a6e5ce5a7c2",
      "event_type": "classification",
      "attribution": "likely_human",
      "confidence": 0.35,
      "llm_score": 0.33,
      "stylo_score": 0.37,
      "status": "classified"
    }
  ]
}
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/submit` | Submit text for attribution analysis |
| POST | `/appeal` | Contest a classification |
| GET | `/log` | View recent audit log entries |
| GET | `/health` | Health check |

### Submit

```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text here...", "creator_id": "user-123"}' | python -m json.tool
```

### Appeal

```bash
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "PASTE-CONTENT-ID", "creator_reasoning": "I wrote this myself..."}' | python -m json.tool
```

---

## Stretch Feature: Ensemble Detection

Implemented **3-signal ensemble** with documented weighting (see `planning.md` § Stretch Features):

| Signal | Weight | What it captures |
|--------|--------|------------------|
| LLM (Groq) | 0.45 | Semantic coherence |
| Stylometric | 0.30 | Sentence/vocabulary structure |
| Rhetorical | 0.25 | Discourse markers & hedging |

**How it works:** Each signal returns a 0–1 AI-likelihood score. The ensemble scorer computes a weighted average, applies disagreement pull when signals diverge, and requires **2-of-3 signal agreement** before issuing a high-confidence AI label.

**Why this helps:** Obvious AI text often triggers both LLM *and* rhetoric signals (formulaic transitions), while human casual writing scores low on all three — improving separation without relying on any single detector.

All three individual scores appear in `/submit` responses and the audit log (`rhetoric_score` field).

---

## Known Limitations

**Formal academic prose** is the most likely misclassification case. Papers and seminar writing have low sentence-length variance and no contractions — exactly the structural patterns our stylometric signal associates with AI. The LLM signal may agree, pushing borderline scores upward. Our mitigation: the uncertain band, disagreement pull, and appeals workflow. In production I'd add a "genre" field so academic submissions skip stylometric uniformity penalties.

---

## Spec Reflection

**How the spec helped:** Writing label variants and score thresholds in `planning.md` before coding prevented a common trap — implementing a binary 0.5 flip. The spec forced me to decide what 0.6 *means* to a user (uncertain, not "probably AI").

**Where implementation diverged:** The spec suggested a simple weighted average, but testing showed the LLM signal alone would flag clearly AI text as high-confidence even when stylometrics disagreed. I added the dual-signal agreement gate for high-confidence AI labels — stricter than the original formula, but better aligned with the false-positive asymmetry the hints emphasized.

---

## AI Usage

1. **Flask app skeleton + Signal 1:** I provided the detection signals section and architecture diagram from `planning.md` and asked for a Flask skeleton with Groq integration. The AI generated a monolithic `app.py`. I split it into `signals/`, `scoring.py`, `labels.py`, and `storage.py` to match my spec's module boundaries.

2. **Confidence scoring logic:** I asked the AI to implement the combine function from my uncertainty representation section. It produced a simple weighted average without the disagreement pull or agreement gate. I added both after testing showed formal human text getting `likely_ai` labels — overriding the AI's simpler version.

---

## Project Structure

```
ai201-project4-provenance-guard/
├── app.py              # Flask routes
├── scoring.py          # Signal combination + thresholds
├── labels.py           # Transparency label text
├── storage.py          # SQLite + audit log
├── signals/
│   ├── llm_signal.py   # Groq-based Signal 1
│   ├── stylometric.py  # Heuristic Signal 2
│   └── rhetorical.py   # Discourse-marker Signal 3 (stretch)
├── planning.md         # Pre-implementation spec
├── seed_samples.py     # Generate sample audit entries
└── requirements.txt
```
