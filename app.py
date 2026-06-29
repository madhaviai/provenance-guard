"""Provenance Guard — AI content attribution backend."""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from labels import generate_label
from scoring import combine_scores, score_to_attribution
from signals.llm_signal import analyze_llm
from signals.rhetorical import analyze_rhetorical
from signals.stylometric import analyze_stylometric
from storage import create_submission, file_appeal, get_audit_log, get_submission, init_db

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

init_db()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    creator_id = (data.get("creator_id") or "").strip()

    if not text:
        return jsonify({"error": "text is required"}), 400
    if not creator_id:
        return jsonify({"error": "creator_id is required"}), 400
    if len(text) > 10000:
        return jsonify({"error": "text exceeds 10,000 character limit"}), 400

    llm_score = analyze_llm(text)
    stylo_score = analyze_stylometric(text)
    rhetoric_score = analyze_rhetorical(text)
    confidence = combine_scores(llm_score, stylo_score, rhetoric_score)
    attribution = score_to_attribution(confidence)
    label = generate_label(confidence, attribution)

    content_id = create_submission(
        creator_id=creator_id,
        text=text,
        attribution=attribution,
        confidence=confidence,
        llm_score=llm_score,
        stylo_score=stylo_score,
        rhetoric_score=rhetoric_score,
        label=label,
    )

    return jsonify(
        {
            "content_id": content_id,
            "attribution": attribution,
            "confidence": confidence,
            "llm_score": llm_score,
            "stylo_score": stylo_score,
            "rhetoric_score": rhetoric_score,
            "label": label,
            "status": "classified",
        }
    )


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = (data.get("content_id") or "").strip()
    creator_reasoning = (data.get("creator_reasoning") or "").strip()

    if not content_id:
        return jsonify({"error": "content_id is required"}), 400
    if not creator_reasoning:
        return jsonify({"error": "creator_reasoning is required"}), 400

    submission = get_submission(content_id)
    if not submission:
        return jsonify({"error": "content not found"}), 404

    result = file_appeal(content_id, creator_reasoning)
    if result and result.get("error") == "appeal_already_filed":
        return jsonify(result), 409

    return jsonify(
        {
            "content_id": content_id,
            "status": "under_review",
            "message": "Appeal received. Your content is now under human review.",
        }
    )


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"entries": get_audit_log(limit=min(limit, 100))})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)
