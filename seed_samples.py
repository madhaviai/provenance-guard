#!/usr/bin/env python3
"""Seed sample audit log entries for documentation and grading."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import app  # noqa: E402

SAMPLES = [
    {
        "text": (
            "Artificial intelligence represents a transformative paradigm shift in modern society. "
            "It is important to note that while the benefits of AI are numerous, it is equally "
            "essential to consider the ethical implications. Furthermore, stakeholders across "
            "various sectors must collaborate to ensure responsible deployment."
        ),
        "creator_id": "demo-ai-sample",
    },
    {
        "text": (
            "ok so i finally tried that new ramen place downtown and honestly? "
            "underwhelming. the broth was fine but they put WAY too much sodium in it and "
            "i was thirsty for like three hours after. my friend got the spicy version and "
            "said it was better. probably won't go back unless someone drags me there"
        ),
        "creator_id": "demo-human-sample",
    },
    {
        "text": (
            "The relationship between monetary policy and asset price inflation has been "
            "extensively studied in the literature. Central banks face a fundamental tension "
            "between their mandate for price stability and the unintended consequences of "
            "prolonged low interest rates on equity and real estate valuations."
        ),
        "creator_id": "demo-borderline-sample",
    },
]


def main():
    with app.test_client() as client:
        content_ids = []
        for sample in SAMPLES:
            resp = client.post("/submit", json=sample)
            data = resp.get_json()
            content_ids.append(data["content_id"])
            print(f"Submitted {data['content_id'][:8]}... → {data['attribution']} ({data['confidence']})")

        appeal_resp = client.post(
            "/appeal",
            json={
                "content_id": content_ids[2],
                "creator_reasoning": (
                    "I wrote this myself for an economics seminar. My writing style is "
                    "formal because it's academic, not because it's AI-generated."
                ),
            },
        )
        print(f"Appeal status: {appeal_resp.get_json()['status']}")

        log_resp = client.get("/log")
        print("\nAudit log entries:")
        print(json.dumps(log_resp.get_json(), indent=2))


if __name__ == "__main__":
    main()
