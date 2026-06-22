# Codex Prompt 01: Bootstrap and harden the starter repo

You are working in the `prompt-router-starter` repository.

## Context

This repo implements a local-first CLI tool for prompt classification and routing. It is intentionally small. The classifier is not an agent; it is a policy-controlled tool that agents and humans can call.

Before changing code, read:

- `AGENTS.md`
- `README.md`
- `docs/01_problem_scenario.md`
- `docs/02_requirements.md`
- `docs/03_architecture.md`
- `docs/05_cli_contract.md`
- `docs/06_policy_and_security.md`

## Task

Harden the starter repo without expanding scope.

Implement or improve:

1. CLI output consistency for all commands.
2. More unit tests for the base routing policy.
3. A small config loader that supports environment variables first and an optional local config file second.
4. JSON schema-like validation helpers for route outputs, using standard library only unless you justify a dependency.
5. Documentation updates if command behavior changes.

## Constraints

- Do not add external LLM calls.
- Do not add semantic vector search yet.
- Do not add central sync yet.
- Do not upload or transmit raw prompts.
- Keep SQLite as the default local database.
- Preserve the existing command names.
- Any new policy behavior must be covered by tests.

## Acceptance criteria

- `python -m unittest discover -s tests` passes.
- `python -m prompt_router status` works.
- `python -m prompt_router classify "Mach daraus eine Tabelle: Max Müller, max@example.com"` returns personal-data classification and internal routing.
- `python -m prompt_router run --dry-run "Fasse diesen öffentlichen Text zusammen"` does not persist an event.
- README and relevant docs remain accurate.

## Review focus

Prefer small, reviewable changes. Do not implement future architecture prematurely.
