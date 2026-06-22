# Starter Repository Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden CLI output, configuration, route validation, policy coverage, and documentation while preserving the starter repository's local-only scope.

**Architecture:** Add one focused configuration module and schema validation helpers, then thread loaded configuration through the existing CLI and database boundaries. Preserve policy branches and command names; cover behavior with standard-library `unittest` tests.

**Tech Stack:** Python 3.10+, standard library (`argparse`, `dataclasses`, `json`, `os`, `pathlib`, `sqlite3`, `unittest`)

---

### Task 1: Configuration loader

**Files:**
- Create: `src/prompt_router/config.py`
- Create: `tests/test_config.py`
- Modify: `src/prompt_router/db.py`

- [ ] **Step 1: Write failing tests for defaults, file loading, environment precedence, and invalid configuration**

Create tests using `tempfile.TemporaryDirectory()` and `unittest.mock.patch.dict()` that assert:

```python
config = load_config(config_path=path, environ={})
self.assertEqual(config.database, expected_database)
self.assertEqual(config.default_sharing_level, "local_only")
self.assertEqual(config.confidence_threshold, 0.90)
```

Also assert that environment values override JSON values and malformed,
unknown, or out-of-range values raise `ConfigError`.

- [ ] **Step 2: Run configuration tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_config -v
```

Expected: failure because `prompt_router.config` does not exist.

- [ ] **Step 3: Implement the minimal loader**

Add:

```python
@dataclass(frozen=True)
class Config:
    database: Path
    default_sharing_level: str
    confidence_threshold: float
    config_file: Path
```

Implement `load_config(config_path=None, environ=None)` with built-in defaults,
optional JSON loading, strict supported-key validation, and environment
overrides. Make `db.default_db_path()` return `load_config().database`.

- [ ] **Step 4: Run configuration tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_config -v
```

Expected: all configuration tests pass.

### Task 2: Route schema validation

**Files:**
- Modify: `src/prompt_router/schemas.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Write failing route-validation tests**

Test valid `RouteDecision.to_dict()` output and invalid cases for missing keys,
wrong types, unknown routes, external-route inconsistency, review inconsistency,
executor inconsistency, and malformed reason codes.

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_schemas -v
```

Expected: failure because validation helpers do not exist.

- [ ] **Step 3: Implement schema-like validation helpers**

Add `SchemaValidationError`, route/executor constants, and:

```python
def validate_route_output(value: Mapping[str, Any]) -> None:
    ...

def validated_route_output(decision: RouteDecision) -> dict[str, Any]:
    payload = decision.to_dict()
    validate_route_output(payload)
    return payload
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_schemas -v
```

Expected: all schema tests pass.

### Task 3: Base policy test coverage

**Files:**
- Modify: `tests/test_classifier_policy.py`

- [ ] **Step 1: Add branch and precedence tests**

Construct `ClassificationResult` values where needed and assert all documented
base routes, review flags, external flags, and secret precedence.

- [ ] **Step 2: Run policy tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_classifier_policy -v
```

Expected: all tests pass because behavior is being characterized, not changed.
If a documented rule fails, adjust only the minimal policy implementation and
rerun the test.

### Task 4: Consistent CLI JSON and configured routing

**Files:**
- Modify: `src/prompt_router/cli.py`
- Modify: `tests/test_cli_db.py`

- [ ] **Step 1: Write failing CLI tests**

Add subprocess tests that assert:

- `redact` emits parseable structured JSON without requiring `--json`;
- `status` reports configured values;
- file configuration applies to `run`;
- environment configuration overrides file configuration;
- configured confidence threshold affects routing;
- expected command errors are JSON;
- dry-run output has no event id and persists no event.

- [ ] **Step 2: Run CLI tests and verify the new tests fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_cli_db -v
```

Expected: failures for plain-text redact and unapplied config settings.

- [ ] **Step 3: Implement CLI integration**

Load config once in `main()`, use it for status, routing threshold, database
connections, and the `run` sharing-level default. Validate every route payload
before printing or persistence. Catch `ConfigError`, `SchemaValidationError`,
and expected `ValueError` failures at the command boundary and emit:

```json
{"error": "message"}
```

Return a non-zero exit status for these failures. Always emit structured JSON
from `redact`; retain `--json` as an accepted no-op.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_cli_db -v
```

Expected: all CLI tests pass.

### Task 5: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/03_architecture.md`
- Modify: `docs/05_cli_contract.md`
- Modify: `docs/06_policy_and_security.md`

- [ ] **Step 1: Update behavior documentation**

Document JSON output for successful commands, config file location and
precedence, supported keys and environment variables, configured confidence
threshold behavior, the `config.py` component, and route validation at the CLI
boundary.

- [ ] **Step 2: Check docs for stale behavior**

Run:

```bash
rg -n "redact|PROMPT_ROUTER_DB|confidence|config.json|plain text" README.md docs
```

Expected: command examples and descriptions agree with implemented behavior.

### Task 6: Full verification

**Files:**
- Review all modified files

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Run acceptance commands against an isolated database**

Run `status`, the required personal-data `classify` command, the required
public-summary dry run, and `events list` with a temporary database.

Expected: status succeeds; classification is `personal_data` with internal
routing; dry-run has no `event_id`; events remain empty.

- [ ] **Step 3: Inspect final changes**

Run:

```bash
find src tests docs -type f -newer README.md -print
```

and manually inspect the changed files because Git metadata is unavailable in
this workspace.
