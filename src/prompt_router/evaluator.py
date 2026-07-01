from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .classifier import classify_prompt
from .constants import CLASSIFIER_VERSION, POLICY_VERSION
from .policy import decide_route


DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "prompt_router_eval_v0_1.schema.json"
)
PII_REASON_CODES = {
    "EMAIL_PATTERN",
    "PHONE_PATTERN",
    "PERSON_NAME_PATTERN",
    "IBAN_PATTERN",
}


class EvaluationError(ValueError):
    """Raised when an evaluation dataset cannot be safely evaluated."""


def load_evaluation_records(
    dataset_path: str | Path,
    *,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> list[dict[str, Any]]:
    path = Path(dataset_path)
    if not path.is_file():
        raise EvaluationError(f"dataset file does not exist: {path}")

    with Path(schema_path).open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as dataset_file:
        for line_number, line in enumerate(dataset_file, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise EvaluationError(
                    f"dataset line {line_number} is not valid JSON: {error.msg}"
                ) from error
            try:
                validator.validate(record)
            except ValidationError as error:
                field = ".".join(str(part) for part in error.absolute_path)
                location = f" at {field}" if field else ""
                raise EvaluationError(
                    f"dataset line {line_number} does not validate{location}: "
                    f"{error.message}"
                ) from error
            records.append(record)

    if not records:
        raise EvaluationError(f"dataset contains no records: {path}")
    return records


def evaluate_dataset(
    dataset_path: str | Path,
    *,
    confidence_threshold: float = 0.90,
) -> dict[str, Any]:
    path = Path(dataset_path)
    records = load_evaluation_records(path)
    counters = {
        "route": 0,
        "sensitivity": 0,
        "task_type": 0,
        "allowed_external": 0,
        "review_flag": 0,
        "false_external": 0,
        "expected_internal": 0,
        "secret_total": 0,
        "secret_detected": 0,
        "pii_total": 0,
        "pii_detected": 0,
        "review_total": 0,
        "review_detected": 0,
        "reason_exact": 0,
        "reason_partial": 0,
        "expected_reason_total": 0,
        "expected_reason_detected": 0,
    }
    failures: list[dict[str, Any]] = []
    false_external_failures: list[dict[str, Any]] = []
    safety_critical_failures: list[dict[str, Any]] = []

    for record in records:
        classification = classify_prompt(record["prompt"])
        decision = decide_route(
            classification,
            confidence_threshold=confidence_threshold,
        )
        actual_reason_codes = set(decision.reason_codes)
        expected_reason_codes = set(record["expected_reason_codes"])

        comparisons = {
            "route": decision.route == record["expected_route"],
            "sensitivity": classification.sensitivity
            == record["sensitivity_label"],
            "task_type": classification.task_type == record["task_type_label"],
            "allowed_external": decision.allowed_external
            == record["expected_allowed_external"],
            "review_flag": decision.should_review == record["requires_review"],
        }
        for name, matches in comparisons.items():
            counters[name] += int(matches)

        false_external = (
            not record["expected_allowed_external"] and decision.allowed_external
        )
        if not record["expected_allowed_external"]:
            counters["expected_internal"] += 1
            counters["false_external"] += int(false_external)

        secret_expected = record["risk_flags"]["has_secrets"]
        secret_detected = (
            classification.contains_secrets
            or decision.route == "block_or_internal_security"
        )
        if secret_expected:
            counters["secret_total"] += 1
            counters["secret_detected"] += int(secret_detected)

        pii_expected = record["risk_flags"]["has_pii"]
        pii_detected = classification.contains_pii or bool(
            actual_reason_codes & PII_REASON_CODES
        )
        if pii_expected:
            counters["pii_total"] += 1
            counters["pii_detected"] += int(pii_detected)

        review_expected = record["requires_review"]
        review_detected = (
            decision.should_review or decision.route == "internal_and_review"
        )
        if review_expected:
            counters["review_total"] += 1
            counters["review_detected"] += int(review_detected)

        reason_exact = actual_reason_codes == expected_reason_codes
        reason_partial = bool(actual_reason_codes & expected_reason_codes) or (
            not actual_reason_codes and not expected_reason_codes
        )
        counters["reason_exact"] += int(reason_exact)
        counters["reason_partial"] += int(reason_partial)
        counters["expected_reason_total"] += len(expected_reason_codes)
        counters["expected_reason_detected"] += len(
            actual_reason_codes & expected_reason_codes
        )

        is_failure = not all(comparisons.values()) or not reason_exact
        is_safety_critical = (
            false_external
            or (secret_expected and not secret_detected)
            or (pii_expected and not pii_detected)
            or (review_expected and not review_detected)
        )
        if is_failure or is_safety_critical:
            detail = _failure_detail(
                record,
                classification=classification,
                decision=decision,
            )
            if is_failure:
                failures.append(detail)
            if false_external:
                false_external_failures.append(detail)
            if is_safety_critical:
                safety_critical_failures.append(detail)

    total = len(records)
    metrics = {
        "route_accuracy": counters["route"] / total,
        "sensitivity_accuracy": counters["sensitivity"] / total,
        "task_type_accuracy": counters["task_type"] / total,
        "allowed_external_accuracy": counters["allowed_external"] / total,
        "review_flag_accuracy": counters["review_flag"] / total,
        "false_external_count": counters["false_external"],
        "false_external_rate": _rate(
            counters["false_external"], counters["expected_internal"], zero=0.0
        ),
        "secret_total": counters["secret_total"],
        "secret_recall": _rate(
            counters["secret_detected"], counters["secret_total"]
        ),
        "pii_total": counters["pii_total"],
        "pii_recall": _rate(counters["pii_detected"], counters["pii_total"]),
        "review_total": counters["review_total"],
        "review_recall": _rate(
            counters["review_detected"], counters["review_total"]
        ),
        "expected_reason_code_recall": _rate(
            counters["expected_reason_detected"],
            counters["expected_reason_total"],
        ),
        "reason_code_exact_match_rate": counters["reason_exact"] / total,
        "reason_code_partial_match_rate": counters["reason_partial"] / total,
    }
    return {
        "dataset": str(path),
        "total_records": total,
        "metrics": metrics,
        "policy_version": POLICY_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "safety_critical_failures": safety_critical_failures,
        "false_external_failures": false_external_failures,
        "failures": failures,
    }


def format_human_report(result: dict[str, Any], *, failure_limit: int = 20) -> str:
    metrics = result["metrics"]
    labels = {
        "route_accuracy": "Route accuracy",
        "sensitivity_accuracy": "Sensitivity accuracy",
        "task_type_accuracy": "Task type accuracy",
        "allowed_external_accuracy": "Allowed external accuracy",
        "review_flag_accuracy": "Review flag accuracy",
        "false_external_count": "False external count",
        "false_external_rate": "False external rate",
        "secret_total": "Secret total",
        "secret_recall": "Secret recall",
        "pii_total": "PII total",
        "pii_recall": "PII recall",
        "review_total": "Review total",
        "review_recall": "Review recall",
        "expected_reason_code_recall": "Expected reason code recall",
        "reason_code_exact_match_rate": "Reason code exact match rate",
        "reason_code_partial_match_rate": "Reason code partial match rate",
    }
    lines = [
        f"Dataset: {result['dataset']}",
        f"Total records: {result['total_records']}",
        f"Classifier version: {result['classifier_version']}",
        f"Policy version: {result['policy_version']}",
        "Metrics:",
    ]
    for key, label in labels.items():
        value = metrics[key]
        rendered = f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(f"  {label}: {rendered}")

    lines.append(
        f"Safety-critical failures: {len(result['safety_critical_failures'])}"
    )
    lines.append(f"False-external failures: {len(result['false_external_failures'])}")

    failures = result["failures"]
    shown = failures[:failure_limit]
    lines.append(f"Failures: {len(failures)} (showing {len(shown)})")
    for failure in shown:
        lines.extend(
            [
                f"  - {failure['id']}: {failure['prompt_excerpt']}",
                f"    route: {failure['expected_route']} -> {failure['actual_route']}",
                "    sensitivity: "
                f"{failure['expected_sensitivity']} -> {failure['actual_sensitivity']}",
                "    task type: "
                f"{failure['expected_task_type']} -> {failure['actual_task_type']}",
                "    allowed external: "
                f"{failure['expected_allowed_external']} -> "
                f"{failure['actual_allowed_external']}",
                "    expected reasons: "
                + ", ".join(failure["expected_reason_codes"]),
                "    actual reasons: "
                + ", ".join(failure["actual_reason_codes"]),
            ]
        )
    return "\n".join(lines)


def _rate(numerator: int, denominator: int, *, zero: float | None = None) -> float | None:
    return numerator / denominator if denominator else zero


def _failure_detail(
    record: dict[str, Any], *, classification: Any, decision: Any
) -> dict[str, Any]:
    prompt = record["prompt"]
    excerpt = prompt if len(prompt) <= 120 else prompt[:117] + "..."
    return {
        "id": record["id"],
        "prompt_excerpt": excerpt,
        "expected_route": record["expected_route"],
        "actual_route": decision.route,
        "expected_sensitivity": record["sensitivity_label"],
        "actual_sensitivity": classification.sensitivity,
        "expected_task_type": record["task_type_label"],
        "actual_task_type": classification.task_type,
        "expected_allowed_external": record["expected_allowed_external"],
        "actual_allowed_external": decision.allowed_external,
        "expected_reason_codes": sorted(record["expected_reason_codes"]),
        "actual_reason_codes": sorted(decision.reason_codes),
    }
