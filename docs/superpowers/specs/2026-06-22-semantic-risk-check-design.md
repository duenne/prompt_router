# Semantic Risk Check Design

## Scope

Add an opt-in, local semantic similarity signal that can only preserve or
increase routing risk. Do not add external embedding calls, a vector database,
default semantic routing, or persistence of vectors and nearest-neighbor
details.

## Components

### Prototype data

Store reviewed prototypes in
`src/prompt_router/data/semantic_examples.json`. Each entry contains:

- a stable identifier;
- a label;
- prototype text;
- whether the label is risk-bearing;
- the sensitivity represented by a risky label.

The first labels are `health`, `employment`, `public_table`, `code`, and
`credentials`. Public-table and code prototypes are non-risk labels. Health,
employment, and credentials are risk labels.

### Deterministic embedder

`semantic.py` exposes a small embedding boundary backed by a deterministic,
fixed-dimensional vector. It normalizes text, emits word and character n-gram
features, hashes each feature with SHA-256 into a vector bucket, and L2
normalizes the resulting counts.

Cosine similarity compares prompt and prototype vectors. This is a placeholder
for a future local embedding adapter, not a claim of production semantic
quality. The implementation and output include a stable model name and version.

### Semantic result

The standalone check returns:

- semantic model and version;
- nearest prototype identifier and label;
- similarity and configured built-in threshold;
- whether the nearest prototype matched;
- whether the match is risk-bearing;
- represented sensitivity when risky;
- semantic reason codes.

A matched risk label emits stable reason codes such as
`SEMANTIC_HEALTH_RISK`. A matched non-risk label may emit an informational
reason code in the standalone result, but informational semantic codes are not
used to authorize external routing.

## Policy integration

`decide_route` accepts an optional semantic result.

1. Without a semantic result, behavior is unchanged.
2. With no matched risk prototype, behavior is unchanged.
3. If a matched risk prototype agrees with an already-sensitive deterministic
   classification, preserve the existing safe route and add semantic reason
   codes.
4. If a matched risk prototype conflicts with deterministic classification,
   return `internal_and_review`, set `allowed_external` to false, set review
   reason `semantic_disagreement`, and add
   `SEMANTIC_DETERMINISTIC_DISAGREEMENT`.
5. A semantic credentials match does not independently select
   `block_or_internal_security`. Only deterministic credential detection can
   select that route.
6. Non-risk prototypes never lower risk, suppress review, or independently
   select `external_llm`.

Agreement means:

- health or employment semantic risk agrees with deterministic
  `sensitive_context`;
- credentials semantic risk agrees with deterministic `credentials`;
- other deterministic sensitivity values disagree with those semantic risks.

## CLI behavior

Add:

```bash
pr semantic-check "Bitte fasse den Krankheitsverlauf dieser Patientin zusammen"
```

Add `--with-semantic-check` to `classify`, `route`, and `run`.

- `semantic-check` returns the complete semantic result.
- `classify --with-semantic-check` includes a top-level `semantic` object and
  uses the semantic-aware route.
- `route --with-semantic-check` preserves the existing route-output schema;
  semantic evidence is represented by route reason codes.
- `run --with-semantic-check` includes a top-level `semantic` object and stores
  final route reason codes in the existing event record.
- Commands without the flag retain current behavior.

## Persistence

Do not create the future `semantic_prompt_features` table in this task.
Semantic reason codes are persisted in the existing `prompt_events.reason_codes`
field because they are part of the final routing decision. Raw prompts and
vectors are not stored by semantic checking.

## Error handling

Prototype loading validates the JSON structure, supported labels, required
fields, and non-empty text. Invalid packaged data raises an explicit semantic
configuration error handled by the CLI's JSON error boundary.

## Testing

Use `unittest` and standard-library subprocess tests to cover:

- deterministic vector output;
- packaged prototype loading;
- health-context semantic matching;
- non-risk public prompt behavior;
- risk disagreement forcing internal review;
- agreement preserving an existing safe route;
- opt-in CLI output;
- unchanged routing without the flag;
- persisted semantic reason codes;
- dry-run behavior remaining non-persistent.

No external dependency is justified.
