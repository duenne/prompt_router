# Starter Repository Hardening Design

## Scope

Harden the existing local-first CLI without adding model providers, semantic
search, central synchronization, or other future architecture. Preserve all
existing command names and SQLite as the default local database.

## CLI output

All successful commands emit valid JSON to standard output. Existing JSON
payload shapes remain stable. The `redact` command changes from plain text by
default to its existing structured object:

```json
{
  "redacted_text": "Schreibe an [PERSON_1] unter [EMAIL_1]",
  "entities": []
}
```

The existing `redact --json` option remains accepted as a compatibility no-op.
Expected command failures emit a JSON object with an `error` string and return
a non-zero exit status. Argument-parser usage errors remain argparse-managed.

## Configuration

Add a focused standard-library configuration loader. The default config path is
`~/.prompt-router/config.json`; `PROMPT_ROUTER_CONFIG` can select another
optional file.

Supported settings are:

| JSON key | Environment override | Default |
|---|---|---|
| `database` | `PROMPT_ROUTER_DB` | `~/.prompt-router/prompt_router.sqlite3` |
| `default_sharing_level` | `PROMPT_ROUTER_DEFAULT_SHARING_LEVEL` | `local_only` |
| `confidence_threshold` | `PROMPT_ROUTER_CONFIDENCE_THRESHOLD` | `0.90` |

Precedence is environment, then config file, then built-in default. Unknown
JSON keys, malformed JSON, wrong value types, an empty sharing level, and a
confidence threshold outside `[0.0, 1.0]` are configuration errors. A missing
config file is valid.

The loaded config controls status output, the default database connection, the
default sharing level for `run`, and the routing confidence threshold. Explicit
function arguments continue to override loaded defaults in library calls.

## Route-output validation

Add standard-library validation helpers beside the route schema. Validation
checks:

- the exact required route-output fields;
- field types;
- allowed route values;
- non-empty string reason codes;
- consistency between route and `allowed_external`;
- consistency between `should_review` and `review_reason`;
- consistency between the selected route and executor.

Validation raises a dedicated `SchemaValidationError`. Route decisions are
validated at the CLI boundary before output and before event persistence. The
helpers are intentionally schema-like and do not introduce a JSON Schema
dependency.

## Policy coverage

The base policy itself remains unchanged except that the confidence threshold
can come from configuration. Unit tests cover:

- credentials taking the security route;
- personal data using an internal small model for simple tasks;
- personal data using the internal LLM for other tasks;
- sensitive context using internal routing and review;
- business-confidential content using internal routing and review;
- ambiguous classifications using internal routing and review;
- otherwise public classifications below the threshold using internal routing
  and review;
- public simple tasks using a specialized executor;
- public non-sensitive tasks allowing the external route;
- secret precedence over all lower-risk rules.

## Testing and documentation

Use `unittest` and subprocess CLI tests. Add focused tests for configuration
precedence and failures, schema validation, policy branches, JSON output, and
dry-run persistence. Update README, architecture, CLI contract, and
policy/security documentation only where behavior or component boundaries
change.

No external dependency is justified for this scope.
