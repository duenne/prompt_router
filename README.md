# Prompt Router Starter

A local-first CLI prototype for classifying prompts, routing them to safe executors, logging decisions, and building a curated training loop for future fast prompt classifiers.

This repository is intentionally small. It is meant to be imported into Codex and extended incrementally rather than overbuilt in the first pass.

## Core idea

Every prompt should pass through a policy-controlled router before it reaches an internal model, external model, specialized executor, or agentic workflow.

```text
User / Agent / CLI
   |
   v
prompt-router
   |
   +-- deterministic checks: PII, secrets, sensitive keywords
   +-- task classification: table, summarize, rewrite, code, agentic, unknown
   +-- policy decision: internal, external, specialized, block/review
   +-- local audit log
   +-- optional review/training dataset flow
```

## Why this exists

Current agent systems often let agents decide which model to call. That creates several problems:

- prompts with personal data may be sent to external models accidentally;
- routing decisions are hard to audit;
- classification mistakes disappear instead of becoming training signals;
- raw prompts are often logged without retention, sharing, or review controls;
- simple tasks such as table formatting are over-served by large models.

This project starts with a conservative local CLI and a SQLite-backed audit log. Future work can add PostgreSQL/pgvector, sync, local model training, and an HTTP gateway.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

pr status
pr classify "Mach daraus eine Tabelle: Max Müller, max@example.com, 0176 123456"
pr route "Fasse diesen öffentlichen Text zusammen"
pr redact "Schreibe an Max Müller unter max@example.com"
pr run --dry-run "Mach daraus eine Tabelle: Max Müller, max@example.com"
pr run "Mach daraus eine Tabelle: Max Müller, max@example.com"
pr events list
```

By default the local SQLite database is created at `~/.prompt-router/prompt_router.sqlite3`. For isolated development:

```bash
export PROMPT_ROUTER_DB=./.local/prompt_router.sqlite3
```

All successful commands write JSON to standard output. `pr redact --json`
remains accepted for compatibility, but `pr redact` now emits the same
structured JSON without the flag.

## Local configuration

The optional local config file is `~/.prompt-router/config.json`. Select a
different file with `PROMPT_ROUTER_CONFIG`. Environment variables take
precedence over file values, and file values take precedence over built-in
defaults.

```json
{
  "database": "~/.prompt-router/prompt_router.sqlite3",
  "default_sharing_level": "local_only",
  "confidence_threshold": 0.9
}
```

Supported environment overrides:

```bash
export PROMPT_ROUTER_DB=./.local/prompt_router.sqlite3
export PROMPT_ROUTER_DEFAULT_SHARING_LEVEL=local_only
export PROMPT_ROUTER_CONFIDENCE_THRESHOLD=0.90
```

Unknown keys and invalid values fail explicitly. The confidence threshold must
be between `0.0` and `1.0`.

## Current implementation scope

Implemented in this starter repo:

- CLI commands: `status`, `classify`, `route`, `redact`, `run`, `events list`, `review list`, `review label`, `dataset build`, `sync --dry-run`.
- Deterministic detection for e-mail, phone-like strings, IBAN-like strings, API-key-like strings, private-key markers, simple person-name patterns, and sensitive context keywords.
- Conservative policy: secrets block; PII/sensitive/business/ambiguous routes internal; public simple table/extract tasks route to specialized executor; public remaining prompts route external.
- Strict standard-library validation for route output objects before CLI output or event persistence.
- Optional JSON configuration with environment-first precedence.
- Local audit logging with reason codes, policy version, classifier version, route, raw prompt storage flag, and redacted prompt.
- Unit and subprocess tests for classification, policy, configuration, schemas, CLI behavior, and persistence.

Not yet implemented:

- production-grade encryption;
- production-grade NER;
- real internal/external LLM execution;
- HTTP gateway;
- PostgreSQL/pgvector;
- central sync API;
- trainable classifier;
- semantic vector checking.

## Important design principle

The classifier is not an agent. It is a deterministic, testable policy component that can be used by agents, CLIs, applications, and gateways. Agents may call it, but production model calls should be forced through it.

## Repository map

```text
AGENTS.md                         Codex instructions for this repo
README.md                         project overview and quickstart
docs/01_problem_scenario.md       current problems and target scenario
docs/02_requirements.md           functional and non-functional requirements
docs/03_architecture.md           target architecture and boundaries
docs/04_data_model.md             local/central/review/training data model
docs/05_cli_contract.md           CLI design and command contract
docs/06_policy_and_security.md    routing policy, privacy, review, sync constraints
docs/07_development_plan.md       phased implementation plan
docs/codex/*.md                   ready-to-use Codex prompts
src/prompt_router/                starter CLI implementation
tests/                            unit tests
```
