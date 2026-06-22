# AGENTS.md

## Project purpose

This repository implements a local-first prompt routing tool. Its job is to classify prompts before they are sent to any LLM or executor, decide the safe route, log the decision locally, and create a controlled path toward reviewed training data.

The tool may be used by humans in the shell, by agents in a CLI workflow, or later as an HTTP gateway. The classifier itself must not become an agent.

## Non-negotiable design constraints

1. No external model call may happen before classification and policy routing.
2. If sensitivity is uncertain, route internally or create review; do not route externally.
3. Raw prompts are local-only by default.
4. Raw prompt upload to a central service must not be implemented as a default path.
5. Training examples must come from reviewed or policy-approved events, preferably redacted or abstracted.
6. Vector similarity, when added, is a risk amplifier, not an external-allow signal.
7. Every routing decision must record classifier version and policy version.
8. Keep the first repo small and runnable. Put long-term design in docs rather than prematurely implementing all infrastructure.

## Preferred implementation style

- Use Python standard library unless a dependency is clearly justified.
- Keep CLI commands stable and explicit.
- Prefer pure functions for detection, classification, and policy decisions.
- Keep security-relevant logic covered by tests.
- Avoid hiding policy decisions in free-form LLM prompts.
- Store reason codes instead of long natural-language rationales.

## Useful commands

```bash
python -m prompt_router status
python -m prompt_router classify "Mach daraus eine Tabelle: Max Müller, max@example.com"
python -m prompt_router route "Fasse diesen öffentlichen Text zusammen"
python -m prompt_router redact "Schreibe an Max Müller unter max@example.com"
python -m prompt_router run --dry-run "Mach daraus eine Tabelle: Max Müller, max@example.com"
python -m unittest discover -s tests
```

## Documentation-first areas

Do not implement these until a dedicated task asks for them:

- PostgreSQL/pgvector migration;
- HTTP API gateway;
- central sync API;
- real model provider integrations;
- semantic embedding checks;
- trainable classifier;
- production encryption.

When implementing one of these, first update the relevant docs and tests.
