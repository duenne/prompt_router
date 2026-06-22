# Semantic Risk Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, deterministic local semantic similarity signal that can only preserve or increase routing risk.

**Architecture:** A packaged JSON prototype set is loaded by a focused `semantic.py` module that creates deterministic hashed feature vectors and returns a typed semantic result. The existing policy accepts that result optionally, while the CLI computes it only for `semantic-check` or explicit `--with-semantic-check` invocations.

**Tech Stack:** Python 3.10+, standard library (`dataclasses`, `hashlib`, `importlib.resources`, `json`, `math`, `re`, `unittest`)

---

### Task 1: Semantic prototype model and deterministic vectors

**Files:**
- Create: `src/prompt_router/data/__init__.py`
- Create: `src/prompt_router/data/semantic_examples.json`
- Create: `src/prompt_router/semantic.py`
- Create: `tests/test_semantic.py`

- [ ] **Step 1: Write failing tests for prototype loading and vector determinism**

Add tests that call:

```python
prototypes = load_prototypes()
self.assertEqual(
    {prototype.label for prototype in prototypes},
    {"health", "employment", "public_table", "code", "credentials"},
)
self.assertEqual(embed_text("Patientenakte"), embed_text("Patientenakte"))
self.assertAlmostEqual(sum(value * value for value in embed_text("Text")), 1.0)
```

Also pass malformed temporary JSON to `load_prototypes(path=...)` and assert
`SemanticConfigError`.

- [ ] **Step 2: Run the semantic tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_semantic -v
```

Expected: import failure because `prompt_router.semantic` does not exist.

- [ ] **Step 3: Add prototype data and minimal embedding implementation**

Create several short German and English prototypes for each required label.
Implement frozen `SemanticPrototype` and `SemanticResult` dataclasses,
`load_prototypes()`, `embed_text()`, and `cosine_similarity()`. Use a
fixed dimension of 128 and SHA-256 bucket assignment for normalized word and
character-trigram features.

- [ ] **Step 4: Run semantic unit tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_semantic -v
```

Expected: prototype and vector tests pass.

### Task 2: Semantic nearest-prototype result

**Files:**
- Modify: `src/prompt_router/semantic.py`
- Modify: `tests/test_semantic.py`

- [ ] **Step 1: Write failing semantic-check behavior tests**

Assert that:

```python
health = semantic_check("Fasse den medizinischen Verlauf und die Behandlung zusammen")
self.assertTrue(health.matched)
self.assertTrue(health.risk_detected)
self.assertEqual(health.label, "health")
self.assertIn("SEMANTIC_HEALTH_RISK", health.reason_codes)
```

Also assert a public table-formatting prompt matches no risk and a clearly
unrelated public prompt cannot produce a risk result below the threshold.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_semantic.SemanticCheckTests -v
```

Expected: failure because `semantic_check` is absent.

- [ ] **Step 3: Implement nearest-prototype checking**

Embed the prompt and all prototypes, select the highest cosine similarity using
stable prototype order as the tie-breaker, and compare against a built-in
threshold. Return model/version metadata, nearest prototype data, rounded
similarity, match/risk flags, represented sensitivity, and stable reason codes.

- [ ] **Step 4: Run semantic behavior tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_semantic -v
```

Expected: all semantic tests pass.

### Task 3: Risk-amplifier policy integration

**Files:**
- Modify: `src/prompt_router/policy.py`
- Modify: `tests/test_classifier_policy.py`

- [ ] **Step 1: Write failing policy tests**

Cover:

- public deterministic classification plus health semantic risk returns
  `internal_and_review` with review reason `semantic_disagreement`;
- deterministic sensitive context plus health semantic risk preserves
  `internal_llm` and includes `SEMANTIC_HEALTH_RISK`;
- non-risk semantic match leaves public external routing unchanged;
- semantic credentials risk against deterministic public classification does
  not select `block_or_internal_security`;
- existing routing without semantic input remains unchanged.

- [ ] **Step 2: Run policy tests and verify semantic cases fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_classifier_policy -v
```

Expected: semantic-aware calls fail because `decide_route` does not accept the
new argument.

- [ ] **Step 3: Implement optional semantic policy logic**

Change the signature to:

```python
def decide_route(
    result: ClassificationResult,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    semantic: SemanticResult | None = None,
) -> RouteDecision:
```

Compute the existing deterministic decision first. If semantic risk agrees,
merge semantic reason codes into that decision. If it disagrees, return
`internal_and_review` with `SEMANTIC_DETERMINISTIC_DISAGREEMENT`. Ignore
non-risk semantic evidence for route authorization.

- [ ] **Step 4: Run policy tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_classifier_policy -v
```

Expected: all policy tests pass.

### Task 4: Opt-in CLI and event reason-code persistence

**Files:**
- Modify: `src/prompt_router/cli.py`
- Modify: `tests/test_cli_db.py`

- [ ] **Step 1: Write failing subprocess tests**

Add tests for:

- `semantic-check` returning a health risk result;
- `classify --with-semantic-check` including `semantic`;
- `route --with-semantic-check` forcing disagreement to internal review;
- route without the flag retaining current deterministic behavior;
- `run --with-semantic-check` persisting semantic reason codes;
- semantic dry run persisting no event.

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_cli_db -v
```

Expected: parser failures for the new command and flags.

- [ ] **Step 3: Implement CLI wiring**

Add `semantic-check`, add `--with-semantic-check` to `classify`, `route`, and
`run`, and introduce a helper that computes semantic data only when requested.
Pass the optional result into `decide_route`. Include `semantic.to_dict()` in
classify/run output only when enabled. Add `SemanticConfigError` to the JSON
error boundary. Event persistence continues to use final decision reason codes.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_cli_db -v
```

Expected: all CLI and persistence tests pass.

### Task 5: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/03_architecture.md`
- Modify: `docs/04_data_model.md`
- Modify: `docs/05_cli_contract.md`
- Modify: `docs/06_policy_and_security.md`
- Modify: `docs/07_development_plan.md`

- [ ] **Step 1: Document semantic behavior and boundaries**

Document the new command and flags, deterministic placeholder vector,
prototype JSON file, risk-amplifier-only policy, disagreement review behavior,
reason-code persistence, and continued deferral of the semantic feature table
and vector database.

- [ ] **Step 2: Check documentation consistency**

Run:

```bash
rg -n "semantic-check|with-semantic-check|risk amplifier|semantic_prompt_features|vector database" README.md docs
```

Expected: all new behavior and deferrals are explicit and consistent.

### Task 6: Full verification

**Files:**
- Review all modified files

- [ ] **Step 1: Run the complete suite**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Run acceptance commands with isolated local state**

Run `semantic-check`, `route --with-semantic-check`, the required health
classification, public no-risk classification, disagreement run, and events
list against a temporary database.

Expected: health semantic risk routes safely; public no-risk behavior remains
unchanged; disagreement routes `internal_and_review`; stored event reason codes
contain semantic evidence.

- [ ] **Step 3: Verify scope**

Run:

```bash
python -m compileall -q src tests
rg -n "requests|httpx|openai|pgvector|CREATE TABLE semantic_prompt_features" src tests pyproject.toml
```

Expected: compilation succeeds and no external API, vector database, or
semantic feature table implementation was added.
