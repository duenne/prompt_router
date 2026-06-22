# 04 Data Model

## Data model principles

1. Separate audit events, review cases, and training examples.
2. Raw prompts are local-only by default.
3. Training examples should be redacted, abstracted, synthetic, or features-only where possible.
4. Every decision must store policy and classifier versions.
5. Sync must be explicit and auditable.

## Prompt events

Prompt events describe what happened at runtime.

```sql
CREATE TABLE prompt_events (
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
```

In a production system, `raw_prompt` should become encrypted storage or be removed from the main table.

## Review cases

Review cases are created from events that are uncertain, risky, disputed, or useful for training.

```sql
CREATE TABLE review_cases (
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
```

## Training examples

Training examples should not be raw audit logs. They should be curated artifacts.

```sql
CREATE TABLE training_examples (
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
```

## Semantic features: future table

```sql
CREATE TABLE semantic_prompt_features (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_model_version TEXT NOT NULL,
    text_source TEXT NOT NULL,
    nearest_neighbors TEXT NULL,
    nearest_sensitive_similarity REAL NULL,
    nearest_public_similarity REAL NULL,
    assigned_cluster TEXT NULL,
    semantic_risk_score REAL NULL,
    semantic_reason_codes TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES prompt_events(id)
);
```

## Sharing levels

| Level | Meaning |
|---|---|
| `local_only` | Nothing leaves local installation. |
| `metrics_only` | Only counters and aggregate metrics may sync. |
| `redacted_example` | Redacted prompt and labels may sync. |
| `abstracted_example` | Only abstracted prompt and labels may sync. |
| `global_training` | Approved example may join global training set. |

## Sync events: future table

```sql
CREATE TABLE sync_events (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    local_event_id TEXT NOT NULL,
    sync_target TEXT NOT NULL,
    sync_status TEXT NOT NULL,
    payload_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    error_message TEXT NULL
);
```
