from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, asdict
from importlib import resources
from pathlib import Path
from typing import Any, Sequence

VECTOR_DIMENSIONS = 128
SEMANTIC_MODEL = "hashed-token-trigram"
SEMANTIC_MODEL_VERSION = "1"
SEMANTIC_MATCH_THRESHOLD = 0.29
SUPPORTED_LABELS = {
    "health",
    "employment",
    "public_table",
    "code",
    "credentials",
}
RISK_SENSITIVITIES = {"sensitive_context", "credentials"}
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class SemanticConfigError(ValueError):
    """Raised when packaged semantic prototype data is invalid."""


@dataclass(frozen=True)
class SemanticPrototype:
    id: str
    label: str
    text: str
    risk: bool
    sensitivity: str | None


@dataclass(frozen=True)
class SemanticResult:
    model: str
    model_version: str
    prototype_id: str | None
    label: str | None
    similarity: float
    threshold: float
    matched: bool
    risk_detected: bool
    sensitivity: str | None
    reason_codes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_prototypes(path: Path | None = None) -> list[SemanticPrototype]:
    try:
        if path is None:
            text = (
                resources.files("prompt_router.data")
                .joinpath("semantic_examples.json")
                .read_text(encoding="utf-8")
            )
        else:
            text = Path(path).read_text(encoding="utf-8")
        value = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise SemanticConfigError(f"invalid semantic prototype data: {exc}") from exc

    if not isinstance(value, list) or not value:
        raise SemanticConfigError("semantic prototype data must be a non-empty array")

    prototypes: list[SemanticPrototype] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise SemanticConfigError(f"semantic prototype {index} must be an object")
        expected_fields = {"id", "label", "text", "risk", "sensitivity"}
        if set(item) != expected_fields:
            raise SemanticConfigError(
                f"semantic prototype {index} must contain exactly {sorted(expected_fields)}"
            )
        prototype_id = item["id"]
        label = item["label"]
        prototype_text = item["text"]
        risk = item["risk"]
        sensitivity = item["sensitivity"]
        if not isinstance(prototype_id, str) or not prototype_id.strip():
            raise SemanticConfigError(f"semantic prototype {index} has invalid id")
        if prototype_id in seen_ids:
            raise SemanticConfigError(f"duplicate semantic prototype id: {prototype_id}")
        if label not in SUPPORTED_LABELS:
            raise SemanticConfigError(f"unsupported semantic label: {label}")
        if not isinstance(prototype_text, str) or not prototype_text.strip():
            raise SemanticConfigError(
                f"semantic prototype {prototype_id} has invalid text"
            )
        if not isinstance(risk, bool):
            raise SemanticConfigError(
                f"semantic prototype {prototype_id} risk must be boolean"
            )
        if risk:
            if sensitivity not in RISK_SENSITIVITIES:
                raise SemanticConfigError(
                    f"semantic prototype {prototype_id} has invalid sensitivity"
                )
        elif sensitivity is not None:
            raise SemanticConfigError(
                f"non-risk semantic prototype {prototype_id} must have null sensitivity"
            )
        seen_ids.add(prototype_id)
        prototypes.append(
            SemanticPrototype(
                id=prototype_id,
                label=label,
                text=prototype_text,
                risk=risk,
                sensitivity=sensitivity,
            )
        )
    return prototypes


def embed_text(text: str, dimensions: int = VECTOR_DIMENSIONS) -> tuple[float, ...]:
    if dimensions <= 0:
        raise ValueError("embedding dimensions must be positive")
    features = _features(text)
    vector = [0.0] * dimensions
    for feature, weight in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:8], "big") % dimensions
        sign = 1.0 if digest[8] & 1 else -1.0
        vector[bucket] += sign * weight
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        return tuple(vector)
    return tuple(value / magnitude for value in vector)


def cosine_similarity(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have equal dimensions")
    similarity = sum(a * b for a, b in zip(left, right))
    return max(0.0, min(1.0, similarity))


def semantic_check(
    text: str,
    *,
    prototypes: Sequence[SemanticPrototype] | None = None,
    threshold: float = SEMANTIC_MATCH_THRESHOLD,
) -> SemanticResult:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("semantic threshold must be between 0.0 and 1.0")
    candidates = list(prototypes) if prototypes is not None else load_prototypes()
    if not candidates:
        raise SemanticConfigError("semantic prototype data must not be empty")

    prompt_vector = embed_text(text)
    nearest = candidates[0]
    nearest_similarity = cosine_similarity(
        prompt_vector,
        embed_text(nearest.text),
    )
    for prototype in candidates[1:]:
        similarity = cosine_similarity(
            prompt_vector,
            embed_text(prototype.text),
        )
        if similarity > nearest_similarity:
            nearest = prototype
            nearest_similarity = similarity

    matched = nearest_similarity >= threshold
    risk_detected = matched and nearest.risk
    if not matched:
        reason_codes = ["SEMANTIC_NO_MATCH"]
    elif nearest.risk:
        reason_codes = [f"SEMANTIC_{nearest.label.upper()}_RISK"]
    else:
        reason_codes = [f"SEMANTIC_{nearest.label.upper()}_MATCH"]

    return SemanticResult(
        model=SEMANTIC_MODEL,
        model_version=SEMANTIC_MODEL_VERSION,
        prototype_id=nearest.id,
        label=nearest.label,
        similarity=round(nearest_similarity, 6),
        threshold=threshold,
        matched=matched,
        risk_detected=risk_detected,
        sensitivity=nearest.sensitivity if risk_detected else None,
        reason_codes=reason_codes,
    )


def _features(text: str) -> list[tuple[str, float]]:
    normalized = " ".join(TOKEN_PATTERN.findall(text.casefold()))
    tokens = normalized.split()
    features = [(f"word:{token}", 3.0) for token in tokens]
    compact = f" {normalized} "
    features.extend(
        (f"tri:{compact[index:index + 3]}", 0.25)
        for index in range(max(0, len(compact) - 2))
    )
    return features
