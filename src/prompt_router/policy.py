from __future__ import annotations

from dataclasses import replace

from .constants import DEFAULT_CONFIDENCE_THRESHOLD
from .schemas import ClassificationResult, RouteDecision
from .semantic import SemanticResult

SIMPLE_TASKS = {"format_table", "extract_entities"}


def decide_route(
    result: ClassificationResult,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    semantic: SemanticResult | None = None,
) -> RouteDecision:
    decision = _decide_deterministic_route(result, confidence_threshold)
    if semantic is None or not semantic.risk_detected:
        return decision

    reason_codes = set(decision.reason_codes)
    reason_codes.update(semantic.reason_codes)
    if _semantic_agrees(result, semantic):
        return replace(decision, reason_codes=sorted(reason_codes))

    reason_codes.add("SEMANTIC_DETERMINISTIC_DISAGREEMENT")
    if decision.route == "block_or_internal_security":
        return replace(decision, reason_codes=sorted(reason_codes))
    reason_codes.discard("PUBLIC_EXTERNAL_ALLOWED")
    reason_codes.discard("PUBLIC_SIMPLE_TASK")
    return RouteDecision(
        route="internal_and_review",
        allowed_external=False,
        should_review=True,
        review_reason="semantic_disagreement",
        executor="internal_llm",
        reason_codes=sorted(reason_codes),
    )


def _semantic_agrees(
    result: ClassificationResult,
    semantic: SemanticResult,
) -> bool:
    if semantic.label in {"health", "employment"}:
        return result.sensitivity == "sensitive_context"
    if semantic.label == "credentials":
        return result.sensitivity == "credentials" or result.contains_secrets
    return True


def _decide_deterministic_route(
    result: ClassificationResult,
    confidence_threshold: float,
) -> RouteDecision:
    reason_codes = set(result.reason_codes)

    if result.contains_secrets or result.sensitivity == "credentials":
        reason_codes.add("SECRET_OR_CREDENTIAL_DETECTED")
        return RouteDecision(
            route="block_or_internal_security",
            allowed_external=False,
            should_review=True,
            review_reason="secret_detected",
            executor="internal_security",
            reason_codes=sorted(reason_codes),
        )

    if result.sensitivity == "personal_data":
        route = "internal_small_model" if result.task_type in SIMPLE_TASKS else "internal_llm"
        reason_codes.add("PERSONAL_DATA_INTERNAL_ONLY")
        return RouteDecision(
            route=route,
            allowed_external=False,
            should_review=False,
            review_reason=None,
            executor=route,
            reason_codes=sorted(reason_codes),
        )

    if result.sensitivity in {"sensitive_context", "business_confidential"}:
        reason_codes.add("SENSITIVE_CONTEXT_INTERNAL_ONLY")
        return RouteDecision(
            route="internal_llm",
            allowed_external=False,
            should_review=True,
            review_reason=result.sensitivity,
            executor="internal_llm",
            reason_codes=sorted(reason_codes),
        )

    if result.sensitivity == "ambiguous" or result.confidence < confidence_threshold:
        reason_codes.add("LOW_CONFIDENCE")
        return RouteDecision(
            route="internal_and_review",
            allowed_external=False,
            should_review=True,
            review_reason="low_confidence",
            executor="internal_llm",
            reason_codes=sorted(reason_codes),
        )

    if result.sensitivity == "public" and result.task_type in SIMPLE_TASKS:
        reason_codes.add("PUBLIC_SIMPLE_TASK")
        return RouteDecision(
            route="specialized_executor",
            allowed_external=False,
            should_review=False,
            review_reason=None,
            executor="specialized_executor",
            reason_codes=sorted(reason_codes),
        )

    reason_codes.add("PUBLIC_EXTERNAL_ALLOWED")
    return RouteDecision(
        route="external_llm",
        allowed_external=True,
        should_review=False,
        review_reason=None,
        executor="external_llm",
        reason_codes=sorted(reason_codes),
    )
