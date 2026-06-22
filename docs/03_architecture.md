# 03 Architecture

## Architectural decision

Implement the prompt classifier/router as a tool and policy component, not as an agent.

Agents can call the tool, but model calls should be forced through the router or gateway. This keeps the privacy decision deterministic, testable, and auditable.

## First repo architecture

```text
CLI
 |
 v
prompt_router.cli
 |
 +-- classifier.py      deterministic sensitivity and task classification
 +-- config.py          optional JSON configuration and environment overrides
 +-- redactor.py        redaction of detected entities
 +-- policy.py          route decision
 +-- db.py              local SQLite audit/review/dataset data
 +-- schemas.py         dataclasses and route-output validation
```

The CLI loads configuration once, classifies the prompt, applies the configured
confidence threshold, validates the route output, and only then prints or
persists the decision. Route validation is implemented with the Python standard
library and does not execute or interpret prompt content.

## Target architecture

```text
Human / Agent / App
        |
        v
Prompt Router / LLM Gateway
        |
        +-- deterministic checks
        +-- lightweight classifier
        +-- task classifier
        +-- semantic similarity check
        +-- policy engine
        +-- redaction engine
        +-- local audit store
        +-- review queue
        +-- dataset builder
        +-- optional sync worker
        |
        +-- internal LLM
        +-- external LLM
        +-- specialized executor
        +-- block/review
```

## Local-first deployment

Each user or team can run a local container with:

- prompt-router service;
- local database;
- optional local vector store;
- local model cache;
- optional sync worker.

```text
Developer machine / team server
  |
  +-- prompt-router container
  +-- postgres or sqlite
  +-- pgvector or vector store later
  +-- policy bundle
  +-- model cache
```

## Central deployment

The central service should not own raw prompts by default. It may own:

- policy registry;
- model registry;
- aggregated metrics;
- reviewed redacted training examples;
- reviewed abstracted training examples;
- global evaluation datasets;
- sync receipts.

## Boundary: local vs central

| Data | Local default | Central default |
|---|---:|---:|
| Raw prompt | yes, optional/temporary | no |
| Redacted prompt | yes | only if shared |
| Abstracted prompt | yes | only if shared |
| Reason codes | yes | yes, if metrics shared |
| Labels | yes | yes, if training shared |
| Embeddings | yes, future | only if explicitly allowed |
| Metrics | yes | optionally |

## Agent integration pattern

Preferred:

```bash
pr run "$PROMPT"
```

Stronger production pattern:

```text
Agent -> OpenAI-compatible gateway endpoint -> prompt-router -> provider
```

The agent thinks it is calling a model endpoint. The gateway enforces classification, routing, redaction, logging, and policy.

## Semantic vector check: future architecture

Vektorprüfung should be added later as a secondary risk signal:

```text
Prompt -> embedding -> nearest labeled examples -> semantic risk score -> policy
```

Important rule:

```text
Vector similarity can increase risk, but it must not be the sole reason to allow external routing.
```
