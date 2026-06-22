# 05 CLI Contract

## Design goals

The CLI is the primary product surface for the first repo. It should be usable by both humans and agents.

Important properties:

- stable command names;
- JSON output for every successful command;
- dry-run support;
- no accidental external calls;
- local logging;
- review and dataset loop.

Expected command failures are also JSON objects with an `error` field and a
non-zero exit status. Argument syntax errors remain managed by `argparse`.

## Command groups

### `pr status`

Show local configuration and version state.

```bash
pr status
```

Expected output:

```json
{
  "mode": "local_first",
  "database": "~/.prompt-router/prompt_router.sqlite3",
  "config_file": "~/.prompt-router/config.json",
  "policy_version": "2026-06-22",
  "classifier_version": "deterministic-0.1.0",
  "confidence_threshold": 0.9,
  "sync_enabled": false,
  "default_sharing_level": "local_only"
}
```

### `pr classify`

Classify prompt sensitivity and task.

```bash
pr classify "Mach daraus eine Tabelle: Max Müller, max@example.com"
```

### `pr route`

Return only the route decision.

```bash
pr route "Fasse diesen öffentlichen Text zusammen"
```

### `pr redact`

Return redacted prompt and entity metadata.

```bash
pr redact "Schreibe an Max Müller unter max@example.com"
```

Output is always structured JSON containing `redacted_text` and `entities`.
The existing `--json` flag remains accepted as a compatibility no-op.

### `pr run`

Classify, route, log, and execute placeholder behavior.

```bash
pr run "Mach daraus eine Tabelle: Max Müller, max@example.com"
```

In the first repo, `run` must not call real external or internal models. It should return a route decision and placeholder executor output.

### `pr run --dry-run`

Show what would happen without persisting an event.

```bash
pr run --dry-run "Schreibe eine Mail an Max Müller"
```

### `pr events list`

List recent local classification events.

```bash
pr events list --limit 20
```

### `pr review list`

List events requiring review.

```bash
pr review list
pr review list --reason low_confidence
```

### `pr review label`

Attach a human label to an event.

```bash
pr review label EVENT_ID \
  --sensitivity personal_data \
  --task-type format_table \
  --route internal_small_model \
  --approve-training \
  --training-text-type redacted
```

### `pr dataset build`

Build JSONL training data from approved examples.

```bash
pr dataset build --output datasets/local-v1.jsonl
```

### `pr sync --dry-run`

Show what would be synchronized centrally. First repo does not perform real sync.

```bash
pr sync --dry-run
```

## Configuration

The CLI reads the optional `~/.prompt-router/config.json` file. A different
file can be selected with `PROMPT_ROUTER_CONFIG`.

Supported file keys and environment overrides:

| JSON key | Environment variable | Default |
|---|---|---|
| `database` | `PROMPT_ROUTER_DB` | `~/.prompt-router/prompt_router.sqlite3` |
| `default_sharing_level` | `PROMPT_ROUTER_DEFAULT_SHARING_LEVEL` | `local_only` |
| `confidence_threshold` | `PROMPT_ROUTER_CONFIDENCE_THRESHOLD` | `0.90` |

Precedence is environment variable, config file, then built-in default.
Malformed JSON, unknown keys, and invalid values cause a JSON error response.

## Reflection comments for shell-based design

```bash
# No model call without classification.
# If uncertain, route internally.
# Raw prompts remain local by default.
# Training data requires review or explicit approval.
# Central sync never uploads raw prompts by default.
# Vector similarity can raise risk, not lower it alone.
# Every decision records policy_version and classifier_version.
```
