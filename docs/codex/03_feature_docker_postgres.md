# Codex Prompt 03: Add Docker and optional PostgreSQL/pgvector backend

You are working in the `prompt-router-starter` repository.

## Context

The first repo uses SQLite by default. We now want a local-first Docker setup that can run with PostgreSQL and prepare for pgvector. This should support the long-term design where each user or team can have a local container with its own database.

Read first:

- `AGENTS.md`
- `docs/03_architecture.md`
- `docs/04_data_model.md`
- `docs/07_development_plan.md`

## Task

Add Docker and optional PostgreSQL support without removing SQLite.

Implement:

1. `Dockerfile` for the CLI/service image.
2. `docker-compose.yml` with:
   - prompt-router container;
   - PostgreSQL container, preferably an image that supports pgvector;
   - named volume for database persistence.
3. A DB abstraction that keeps SQLite as default but can connect to PostgreSQL when `PROMPT_ROUTER_DATABASE_URL` is set.
4. Migration/init logic for both SQLite and PostgreSQL.
5. Documentation for local startup:

   ```bash
   docker compose up -d
   docker compose run --rm prompt-router pr status
   ```

6. A clear note that production encryption, IAM, backup policy, and retention enforcement are still future work.

## Constraints

- Do not implement central sync.
- Do not upload raw prompts.
- Do not make PostgreSQL mandatory for local CLI use.
- Keep all existing tests passing.
- Add tests for DB URL parsing or initialization if possible without requiring a running Postgres instance.

## Acceptance criteria

- Existing SQLite workflow still works.
- Docker image builds.
- Compose file is documented.
- `README.md` explains SQLite default and PostgreSQL optional mode.
- No raw-prompt centralization path is introduced.
