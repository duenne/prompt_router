from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

ROUTE_EXECUTORS = {
    "block_or_internal_security": "internal_security",
    "internal_llm": "internal_llm",
    "internal_small_model": "internal_small_model",
    "specialized_executor": "specialized_executor",
    "external_llm": "external_llm",
    "internal_and_review": "internal_llm",
}
ROUTE_OUTPUT_FIELDS = {
    "route",
    "allowed_external",
    "should_review",
    "review_reason",
    "executor",
    "reason_codes",
}
REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class SchemaValidationError(ValueError):
    """Raised when a route output does not match the CLI contract."""


@dataclass(frozen=True)
class Entity:
    type: str
    start: int
    end: int
    text: str
    replacement: str
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    entities: list[Entity]

    def to_dict(self) -> dict[str, Any]:
        return {
            "redacted_text": self.redacted_text,
            "entities": [e.to_dict() for e in self.entities],
        }


@dataclass(frozen=True)
class ClassificationResult:
    sensitivity: str
    contains_pii: bool
    contains_secrets: bool
    business_confidential: bool
    pii_types: list[str]
    task_type: str
    complexity: str
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    redacted_prompt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouteDecision:
    route: str
    allowed_external: bool
    should_review: bool
    review_reason: str | None
    executor: str
    reason_codes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_route_output(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise SchemaValidationError("route output must be an object")

    fields = set(value)
    missing = sorted(ROUTE_OUTPUT_FIELDS - fields)
    extra = sorted(fields - ROUTE_OUTPUT_FIELDS)
    if missing:
        raise SchemaValidationError(f"route output missing field: {missing[0]}")
    if extra:
        raise SchemaValidationError(f"route output has unknown field: {extra[0]}")

    route = value["route"]
    if not isinstance(route, str):
        raise SchemaValidationError("route must be a string")
    if route not in ROUTE_EXECUTORS:
        raise SchemaValidationError(f"unsupported route: {route}")

    allowed_external = value["allowed_external"]
    if not isinstance(allowed_external, bool):
        raise SchemaValidationError("allowed_external must be a boolean")
    expected_external = route == "external_llm"
    if allowed_external != expected_external:
        raise SchemaValidationError(
            "allowed_external must be true only for external_llm"
        )

    should_review = value["should_review"]
    if not isinstance(should_review, bool):
        raise SchemaValidationError("should_review must be a boolean")
    review_reason = value["review_reason"]
    if review_reason is not None and not isinstance(review_reason, str):
        raise SchemaValidationError("review_reason must be a string or null")
    if should_review and not review_reason:
        raise SchemaValidationError(
            "review_reason must be set when should_review is true"
        )
    if not should_review and review_reason is not None:
        raise SchemaValidationError(
            "review_reason must be null when should_review is false"
        )

    executor = value["executor"]
    if not isinstance(executor, str):
        raise SchemaValidationError("executor must be a string")
    expected_executor = ROUTE_EXECUTORS[route]
    if executor != expected_executor:
        raise SchemaValidationError(
            f"executor must be {expected_executor!r} for route {route!r}"
        )

    reason_codes = value["reason_codes"]
    if not isinstance(reason_codes, list):
        raise SchemaValidationError("reason_codes must be an array")
    if not all(
        isinstance(code, str) and REASON_CODE_PATTERN.fullmatch(code)
        for code in reason_codes
    ):
        raise SchemaValidationError(
            "reason_codes must contain only non-empty uppercase codes"
        )


def validated_route_output(decision: RouteDecision) -> dict[str, Any]:
    payload = decision.to_dict()
    validate_route_output(payload)
    return payload
