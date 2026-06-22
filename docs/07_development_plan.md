# 07 Development Plan

## Balance between first repo and future prompts

The first repo should be useful but not overbuilt. It should establish:

- the product vocabulary;
- the CLI contract;
- the data model shape;
- deterministic routing logic;
- local logging;
- test structure;
- Codex instructions.

It should not attempt to solve production infrastructure immediately. PostgreSQL, vector search, real LLM providers, sync, and training are separate feature tasks.

## Phase 0: repository scaffold

Deliver:

- Markdown requirements and architecture docs;
- `AGENTS.md`;
- Python package;
- CLI commands;
- SQLite local database;
- unit tests;
- ready-to-use Codex prompts.

## Phase 1: harden local CLI

Deliver:

- better tests;
- more reason codes;
- config file support;
- retention settings;
- export/import of local events;
- JSON schemas for CLI output.

## Phase 2: semantic risk check

First increment delivered:

- deterministic local embedding interface;
- packaged local labeled prototypes and in-memory nearest-prototype comparison;
- `pr semantic-check` command;
- opt-in policy integration as a risk amplifier;
- semantic reason-code persistence in existing events.

Still deferred:

- pluggable vector backend;
- vector database or persistent nearest-neighbor store;
- production local embedding model;
- semantic feature table persistence.

## Phase 3: Docker + PostgreSQL/pgvector

Deliver:

- Dockerfile;
- docker-compose with PostgreSQL and pgvector;
- database migration layer;
- environment-based DB selection;
- tests for SQLite and Postgres if practical.

## Phase 4: HTTP gateway

Deliver:

- FastAPI or equivalent HTTP API;
- OpenAI-compatible gateway endpoint if desired;
- route enforcement;
- agent-safe integration;
- request/response audit.

## Phase 5: central sync

Deliver:

- sync API contract;
- local sync worker;
- sharing levels;
- dry-run and receipt log;
- no raw prompt upload by default.

## Phase 6: training loop

Deliver:

- reviewed dataset builder;
- trainable fast classifier;
- evaluation reports;
- false-negative focused promotion gate;
- model registry integration.

## Suggested implementation rule

Each Codex task should be small enough to review as one pull request. Prefer documents plus tests over large speculative implementations.
