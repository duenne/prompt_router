from __future__ import annotations

import re
from collections import defaultdict

from .schemas import Entity, RedactionResult

PATTERNS: list[tuple[str, str, str]] = [
    ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "EMAIL_PATTERN"),
    ("IBAN", r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", "IBAN_PATTERN"),
    ("PRIVATE_KEY", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "PRIVATE_KEY_MARKER"),
    ("API_KEY", r"\b(?:sk|pk|rk|api)[-_][A-Za-z0-9]{16,}\b", "API_KEY_PATTERN"),
    ("PHONE", r"(?<!\w)(?:\+\d{1,3}[\s\-/]?)?(?:\(?\d{2,5}\)?[\s\-/]?){2,}\d{2,}(?!\w)", "PHONE_PATTERN"),
]

# Deliberately conservative and imperfect. This is a placeholder until a real NER model is added.
PERSON_NAME_PATTERN = re.compile(r"\b[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+\b")


def _overlaps(candidate: tuple[int, int], existing: list[Entity]) -> bool:
    start, end = candidate
    return any(start < item.end and end > item.start for item in existing)


def detect_entities(text: str) -> list[Entity]:
    entities: list[Entity] = []

    for entity_type, pattern, reason_code in PATTERNS:
        for match in re.finditer(pattern, text):
            if _overlaps((match.start(), match.end()), entities):
                continue
            entities.append(
                Entity(
                    type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    replacement="",
                    reason_code=reason_code,
                )
            )

    for match in PERSON_NAME_PATTERN.finditer(text):
        # Avoid matching known phrases in examples too aggressively.
        matched = match.group(0)
        if matched.lower() in {"mach daraus", "bitte fasse", "schreibe eine"}:
            continue
        if _overlaps((match.start(), match.end()), entities):
            continue
        entities.append(
            Entity(
                type="PERSON",
                start=match.start(),
                end=match.end(),
                text=matched,
                replacement="",
                reason_code="PERSON_NAME_PATTERN",
            )
        )

    entities.sort(key=lambda item: (item.start, item.end))

    counters: defaultdict[str, int] = defaultdict(int)
    with_replacements: list[Entity] = []
    for entity in entities:
        counters[entity.type] += 1
        replacement = f"[{entity.type}_{counters[entity.type]}]"
        with_replacements.append(
            Entity(
                type=entity.type,
                start=entity.start,
                end=entity.end,
                text=entity.text,
                replacement=replacement,
                reason_code=entity.reason_code,
            )
        )
    return with_replacements


def redact(text: str) -> RedactionResult:
    entities = detect_entities(text)
    if not entities:
        return RedactionResult(redacted_text=text, entities=[])

    output: list[str] = []
    cursor = 0
    for entity in entities:
        output.append(text[cursor:entity.start])
        output.append(entity.replacement)
        cursor = entity.end
    output.append(text[cursor:])
    return RedactionResult(redacted_text="".join(output), entities=entities)
