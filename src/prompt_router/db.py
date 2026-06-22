from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .constants import CLASSIFIER_VERSION, DEFAULT_SHARING_LEVEL, POLICY_VERSION
from .schemas import ClassificationResult, RouteDecision


def default_db_path() -> Path:
    return load_config().database


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS prompt_events (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            raw_prompt TEXT NULL,
            raw_prompt_stored INTEGER NOT NULL DEFAULT 0,
            redacted_prompt TEXT NULL,
            sensitivity TEXT NOT NULL,
            contains_pii INTEGER NOT NULL,
            contains_secrets INTEGER NOT NULL,
            business_confidential INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            complexity TEXT NOT NULL,
            route TEXT NOT NULL,
            allowed_external INTEGER NOT NULL,
            confidence REAL NOT NULL,
            reason_codes TEXT NOT NULL,
            classifier_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            should_review INTEGER NOT NULL DEFAULT 0,
            review_reason TEXT NULL,
            review_status TEXT NOT NULL DEFAULT 'none',
            sharing_level TEXT NOT NULL DEFAULT 'local_only'
        );

        CREATE TABLE IF NOT EXISTS review_cases (
            id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            priority TEXT NOT NULL,
            review_status TEXT NOT NULL,
            reviewer_label TEXT NULL,
            reviewer_notes TEXT NULL,
            reviewed_at TEXT NULL,
            approved_for_training INTEGER NOT NULL DEFAULT 0,
            training_text_type TEXT NULL,
            FOREIGN KEY(event_id) REFERENCES prompt_events(id)
        );

        CREATE TABLE IF NOT EXISTS training_examples (
            id TEXT PRIMARY KEY,
            review_case_id TEXT NULL,
            event_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            training_text TEXT NOT NULL,
            training_text_type TEXT NOT NULL,
            label TEXT NOT NULL,
            dataset_version TEXT NULL,
            source_policy_version TEXT NOT NULL,
            source_classifier_version TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES prompt_events(id)
        );
        """
    )
    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_event(
    conn: sqlite3.Connection,
    *,
    prompt_hash: str,
    prompt: str,
    store_raw: bool,
    classification: ClassificationResult,
    decision: RouteDecision,
    sharing_level: str = DEFAULT_SHARING_LEVEL,
) -> str:
    event_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO prompt_events (
            id, created_at, prompt_hash, raw_prompt, raw_prompt_stored, redacted_prompt,
            sensitivity, contains_pii, contains_secrets, business_confidential,
            task_type, complexity, route, allowed_external, confidence, reason_codes,
            classifier_version, policy_version, should_review, review_reason,
            review_status, sharing_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            now_iso(),
            prompt_hash,
            prompt if store_raw else None,
            1 if store_raw else 0,
            classification.redacted_prompt,
            classification.sensitivity,
            int(classification.contains_pii),
            int(classification.contains_secrets),
            int(classification.business_confidential),
            classification.task_type,
            classification.complexity,
            decision.route,
            int(decision.allowed_external),
            classification.confidence,
            json.dumps(decision.reason_codes, ensure_ascii=False),
            CLASSIFIER_VERSION,
            POLICY_VERSION,
            int(decision.should_review),
            decision.review_reason,
            "pending" if decision.should_review else "none",
            sharing_level,
        ),
    )
    if decision.should_review:
        create_review_case(conn, event_id=event_id, reason=decision.review_reason or "review")
    conn.commit()
    return event_id


def create_review_case(conn: sqlite3.Connection, *, event_id: str, reason: str) -> str:
    case_id = str(uuid.uuid4())
    priority = "high" if reason in {"secret_detected", "low_confidence"} else "medium"
    conn.execute(
        """
        INSERT INTO review_cases (
            id, event_id, created_at, priority, review_status
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (case_id, event_id, now_iso(), priority, "pending"),
    )
    return case_id


def list_events(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, created_at, sensitivity, task_type, route, confidence,
               should_review, review_status, sharing_level, reason_codes
        FROM prompt_events
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_review_cases(conn: sqlite3.Connection, reason: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    query = """
        SELECT rc.id AS review_case_id, pe.id AS event_id, pe.created_at,
               pe.sensitivity, pe.task_type, pe.route, pe.review_reason,
               rc.priority, rc.review_status, pe.redacted_prompt
        FROM review_cases rc
        JOIN prompt_events pe ON pe.id = rc.event_id
        WHERE rc.review_status = 'pending'
    """
    params: list[Any] = []
    if reason:
        query += " AND pe.review_reason = ?"
        params.append(reason)
    query += " ORDER BY pe.created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def label_review_case(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    label: dict[str, Any],
    notes: str | None,
    approve_training: bool,
    training_text_type: str,
) -> dict[str, Any]:
    event = conn.execute("SELECT * FROM prompt_events WHERE id = ?", (event_id,)).fetchone()
    if event is None:
        raise ValueError(f"event not found: {event_id}")

    review = conn.execute("SELECT * FROM review_cases WHERE event_id = ?", (event_id,)).fetchone()
    if review is None:
        case_id = create_review_case(conn, event_id=event_id, reason="manual_label")
        review = conn.execute("SELECT * FROM review_cases WHERE id = ?", (case_id,)).fetchone()

    conn.execute(
        """
        UPDATE review_cases
        SET review_status = 'reviewed', reviewer_label = ?, reviewer_notes = ?,
            reviewed_at = ?, approved_for_training = ?, training_text_type = ?
        WHERE event_id = ?
        """,
        (
            json.dumps(label, ensure_ascii=False),
            notes,
            now_iso(),
            int(approve_training),
            training_text_type if approve_training else None,
            event_id,
        ),
    )
    conn.execute("UPDATE prompt_events SET review_status = 'reviewed' WHERE id = ?", (event_id,))

    training_id: str | None = None
    if approve_training:
        training_id = add_training_example(conn, event=event, review_case_id=review["id"], label=label, text_type=training_text_type)

    conn.commit()
    return {"event_id": event_id, "review_status": "reviewed", "training_example_id": training_id}


def add_training_example(
    conn: sqlite3.Connection,
    *,
    event: sqlite3.Row,
    review_case_id: str,
    label: dict[str, Any],
    text_type: str,
) -> str:
    if text_type == "raw":
        training_text = event["raw_prompt"]
        if not training_text:
            raise ValueError("raw training text requested, but raw prompt was not stored")
    elif text_type == "redacted":
        training_text = event["redacted_prompt"]
    elif text_type == "features_only":
        training_text = json.dumps(
            {
                "sensitivity": event["sensitivity"],
                "task_type": event["task_type"],
                "reason_codes": json.loads(event["reason_codes"]),
            },
            ensure_ascii=False,
        )
    else:
        raise ValueError(f"unsupported training_text_type: {text_type}")

    if not training_text:
        raise ValueError("training text is empty")

    training_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO training_examples (
            id, review_case_id, event_id, created_at, training_text, training_text_type,
            label, dataset_version, source_policy_version, source_classifier_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            training_id,
            review_case_id,
            event["id"],
            now_iso(),
            training_text,
            text_type,
            json.dumps(label, ensure_ascii=False),
            None,
            event["policy_version"],
            event["classifier_version"],
        ),
    )
    return training_id


def training_examples(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, training_text, training_text_type, label,
               source_policy_version, source_classifier_version
        FROM training_examples
        ORDER BY created_at ASC
        """
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def sync_plan(conn: sqlite3.Connection, limit: int = 50) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT id, sensitivity, task_type, route, sharing_level, review_status
        FROM prompt_events
        WHERE sharing_level != 'local_only'
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return {
        "sync_supported": False,
        "dry_run_only": True,
        "candidate_count": len(rows),
        "candidates": [_row_to_dict(row) for row in rows],
        "note": "Real central sync is intentionally out of scope for the starter repo.",
    }


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    if "reason_codes" in result and isinstance(result["reason_codes"], str):
        try:
            result["reason_codes"] = json.loads(result["reason_codes"])
        except json.JSONDecodeError:
            pass
    if "reviewer_label" in result and isinstance(result["reviewer_label"], str):
        try:
            result["reviewer_label"] = json.loads(result["reviewer_label"])
        except json.JSONDecodeError:
            pass
    if "label" in result and isinstance(result["label"], str):
        try:
            result["label"] = json.loads(result["label"])
        except json.JSONDecodeError:
            pass
    return result
