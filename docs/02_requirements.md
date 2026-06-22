# 02 Requirements

## Product requirement summary

Build a local-first prompt routing tool that classifies prompts, decides a safe execution route, logs the decision, and enables controlled review and training-data generation.

The tool must be usable by:

- humans in a shell;
- coding agents and other agent systems;
- later, applications through an HTTP gateway.

The first repo should implement the CLI and local audit loop. More complex infrastructure belongs in later feature prompts.

## Functional requirements

### FR-001 Classify prompt sensitivity

The tool must classify prompt sensitivity into at least:

- `public`
- `personal_data`
- `sensitive_context`
- `business_confidential`
- `credentials`
- `ambiguous`

### FR-002 Detect PII and secrets deterministically

The first implementation must include deterministic checks for:

- e-mail addresses;
- phone-like values;
- IBAN-like values;
- API-key-like values;
- private-key markers;
- simple person-name patterns;
- selected sensitive context keywords.

These checks are intentionally conservative and should produce reason codes.

### FR-003 Classify task type

The tool must classify task type into at least:

- `format_table`
- `extract_entities`
- `summarize`
- `rewrite`
- `write_email`
- `classify`
- `code`
- `agentic_task`
- `unknown`

### FR-004 Decide route through policy

The policy engine must decide among:

- `block_or_internal_security`
- `internal_llm`
- `internal_small_model`
- `specialized_executor`
- `external_llm`
- `internal_and_review`

The policy must be conservative:

- credentials must not be sent externally;
- personal data must not be sent externally;
- sensitive context must not be sent externally;
- business-confidential prompts must not be sent externally;
- ambiguous or low-confidence prompts must route internally or to review;
- public simple tasks may use specialized executors;
- public non-sensitive prompts may route externally.

### FR-005 Redact prompts

The tool must produce a redacted text representation and entity metadata. Redaction should preserve task semantics where possible while replacing detected PII/secrets with placeholders.

### FR-006 Log classification events locally

The tool must store local audit events including:

- event id;
- timestamp;
- prompt hash;
- raw prompt storage flag;
- redacted prompt;
- sensitivity;
- task type;
- route;
- allowed-external flag;
- confidence;
- reason codes;
- classifier version;
- policy version;
- review flags;
- sharing level.

### FR-007 Support review cases

The tool must support listing events requiring review and applying human labels.

### FR-008 Build datasets from approved examples

The tool must create JSONL datasets from events that were reviewed or explicitly approved. Raw prompt datasets must not be the default.

### FR-009 Support dry-run behavior

The tool must allow users and agents to see what would happen without executing or logging a full run.

### FR-010 Support future sync model

The data model and CLI should anticipate local-to-central sync, but the first implementation should only support dry-run sync. Default sharing level must be `local_only`.

## Non-functional requirements

### NFR-001 Low latency

The classification path should be designed for short inference. The first implementation uses deterministic logic. Future ML models should be small, local, and fast.

### NFR-002 Auditability

Every decision must be reproducible via versioned policy, classifier version, and reason codes.

### NFR-003 Security by default

No raw prompt should leave the local environment by default. Central sync must require explicit sharing level and should prefer redacted or abstracted text.

### NFR-004 Agent-safe design

The tool may be called by agents, but agents must not be trusted to enforce privacy policy. Production external model credentials should live behind a gateway, not inside the agent.

### NFR-005 Evolvability

The system should allow adding:

- PostgreSQL/pgvector;
- HTTP gateway;
- trainable classifier;
- semantic similarity checks;
- central sync;
- model and policy registry.

### NFR-006 Testability

The detection and routing logic must be covered by unit tests. Any change to routing policy should add or update tests.

## Out of scope for first repo

The first repo should not implement:

- production encryption;
- external LLM calls;
- real internal LLM calls;
- vector database;
- federated learning;
- central backend;
- browser UI;
- enterprise IAM.
