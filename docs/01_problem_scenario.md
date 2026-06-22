# 01 Problem Scenario

## Today: fragile prompt routing in agent systems

Many agent systems let an agent or developer code directly decide which model to call.

```bash
# Today: the agent directly calls an external model.
agent run "Mach mir daraus eine Tabelle: Max Müller, max@example.com, 0176 123456"
```

This creates a security and compliance problem. The prompt contains personal data, but the agent might route it to an external model because the requested task looks simple.

## Problems

### 1. PII and confidential content are not reliably detected

Simple prompts can contain sensitive data:

```text
Mach daraus eine Tabelle: Max Müller, max@example.com, 0176 123456
```

The task is simple, but the content is not safe for external routing.

### 2. Agents are too flexible for policy enforcement

An agent can reason, plan, and call tools. That is useful for task execution, but bad as the primary privacy gate. The privacy gate should be deterministic, testable, auditable, and conservative.

### 3. Decisions are not reproducible

Without a route event containing policy version, classifier version, reason codes, and confidence, it is difficult to explain why a prompt was routed internally, externally, blocked, or sent to a specialized executor.

### 4. Mistakes are not converted into training data

When a classifier makes a wrong decision, the system should create a review case and eventually a labeled training example. Today those mistakes usually disappear.

### 5. Raw prompt logging is risky

A system that stores all raw prompts centrally may create a high-value sensitive data store. Raw prompts should remain local by default, be encrypted or avoided, and have retention rules.

### 6. Simple tasks are over-served

Some prompts ask for simple transformations:

```text
Mach daraus eine Tabelle.
Extrahiere die E-Mail-Adressen.
Formatiere dieses JSON.
```

These may be handled by deterministic logic or small local executors after privacy classification.

## Target scenario

```bash
# Safer: every prompt goes through prompt-router.
pr run "Mach daraus eine Tabelle: Max Müller, max@example.com, 0176 123456"
```

The router performs:

1. deterministic checks for PII, secrets, and sensitive context;
2. task classification;
3. optional semantic similarity check in later versions;
4. policy decision;
5. local audit logging;
6. optional review/training workflow.

Expected decision:

```json
{
  "sensitivity": "personal_data",
  "task_type": "format_table",
  "route": "internal_small_model",
  "allowed_external": false,
  "reason_codes": ["EMAIL_PATTERN", "PHONE_PATTERN", "PERSON_NAME_PATTERN"]
}
```

## Long-term product shape

The tool should support three deployment modes:

1. local CLI for individual users;
2. local-first Docker container with local database per user or team;
3. centralized gateway and training backend for organizations.

Raw prompts should be owned by the local installation. Central systems receive only metrics, redacted examples, abstracted examples, or reviewed training examples according to explicit sharing rules.
