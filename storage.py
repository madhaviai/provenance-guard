"""SQLite persistence for submissions and audit log."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "provenance_guard.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                content_id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                text TEXT NOT NULL,
                attribution TEXT NOT NULL,
                confidence REAL NOT NULL,
                llm_score REAL NOT NULL,
                stylo_score REAL NOT NULL,
                rhetoric_score REAL NOT NULL DEFAULT 0.5,
                label TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'classified',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                creator_id TEXT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(submissions)")}
        if "rhetoric_score" not in cols:
            conn.execute(
                "ALTER TABLE submissions ADD COLUMN rhetoric_score REAL NOT NULL DEFAULT 0.5"
            )


def create_submission(
    creator_id: str,
    text: str,
    attribution: str,
    confidence: float,
    llm_score: float,
    stylo_score: float,
    rhetoric_score: float,
    label: str,
) -> str:
    content_id = str(uuid.uuid4())
    now = _utc_now()
    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": now,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylo_score": stylo_score,
        "rhetoric_score": rhetoric_score,
        "label": label,
        "status": "classified",
    }

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO submissions
            (content_id, creator_id, text, attribution, confidence,
             llm_score, stylo_score, rhetoric_score, label, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'classified', ?, ?)
            """,
            (
                content_id,
                creator_id,
                text,
                attribution,
                confidence,
                llm_score,
                stylo_score,
                rhetoric_score,
                label,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO audit_log (content_id, creator_id, event_type, timestamp, payload)
            VALUES (?, ?, 'classification', ?, ?)
            """,
            (content_id, creator_id, now, json.dumps(entry)),
        )

    return content_id


def get_submission(content_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE content_id = ?", (content_id,)
        ).fetchone()
    if not row:
        return None
    return dict(row)


def file_appeal(content_id: str, creator_reasoning: str) -> dict | None:
    submission = get_submission(content_id)
    if not submission:
        return None
    if submission["status"] == "under_review":
        return {"error": "appeal_already_filed", "content_id": content_id}

    now = _utc_now()
    appeal_entry = {
        "content_id": content_id,
        "creator_id": submission["creator_id"],
        "timestamp": now,
        "event_type": "appeal",
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "original_attribution": submission["attribution"],
        "original_confidence": submission["confidence"],
        "llm_score": submission["llm_score"],
        "stylo_score": submission["stylo_score"],
        "rhetoric_score": submission.get("rhetoric_score", 0.5),
    }

    with get_db() as conn:
        conn.execute(
            "UPDATE submissions SET status = 'under_review', updated_at = ? WHERE content_id = ?",
            (now, content_id),
        )
        conn.execute(
            """
            INSERT INTO audit_log (content_id, creator_id, event_type, timestamp, payload)
            VALUES (?, ?, 'appeal', ?, ?)
            """,
            (
                content_id,
                submission["creator_id"],
                now,
                json.dumps(appeal_entry),
            ),
        )

    return appeal_entry


def get_audit_log(limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT content_id, creator_id, event_type, timestamp, payload
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    entries = []
    for row in rows:
        payload = json.loads(row["payload"])
        entries.append(
            {
                "content_id": row["content_id"],
                "creator_id": row["creator_id"],
                "event_type": row["event_type"],
                "timestamp": row["timestamp"],
                **payload,
            }
        )
    return entries
