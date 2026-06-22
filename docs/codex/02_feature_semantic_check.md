# Codex Prompt 02: Add semantic risk check as a secondary signal

You are working in the `prompt-router-starter` repository.

## Context

The current router uses deterministic checks and a conservative policy. We now want to add a first version of semantic risk checking. This feature should prepare the architecture for vector-based classification without requiring external embedding APIs.

Read first:

- `AGENTS.md`
- `docs/03_architecture.md`
- `docs/04_data_model.md`
- `docs/06_policy_and_security.md`
- `docs/07_development_plan.md`

## Task

Add a minimal semantic risk check feature.

Implement:

1. A new module, for example `semantic.py`.
2. A local deterministic placeholder embedding or feature-vector representation using standard library only.
3. A small local semantic examples table or JSON file with labeled prototypes, such as:
   - health context;
   - HR/employment context;
   - public table formatting;
   - code generation;
   - credentials/security context.
4. A command:

   ```bash
   pr semantic-check "Bitte fasse den Krankheitsverlauf dieser Patientin zusammen"
   ```

5. Policy integration behind an explicit flag first:

   ```bash
   pr route --with-semantic-check "..."
   pr classify --with-semantic-check "..."
   pr run --with-semantic-check "..."
   ```

6. Semantic risk must only increase risk. It must not independently allow external routing.
7. Store semantic reason codes in the event reason codes when the semantic flag is used.

## Constraints

- Do not call external embedding APIs.
- Do not add a vector database in this task.
- Do not make semantic check the default yet.
- Do not weaken deterministic or policy-based routing.
- If semantic risk and deterministic classification disagree, route internally and mark for review.

## Acceptance criteria

- New tests cover semantic health-context routing.
- New tests cover public prompts that remain public when semantic check finds no risk.
- New tests cover disagreement behavior.
- `python -m unittest discover -s tests` passes.
- CLI docs are updated.

## Important policy rule

Vector or semantic similarity is a risk amplifier, not an allow signal.
