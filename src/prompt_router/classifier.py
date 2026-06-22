from __future__ import annotations

import re

from .redactor import redact
from .schemas import ClassificationResult

SENSITIVE_CONTEXT_KEYWORDS = {
    "health": ["krank", "krankheit", "patient", "patientin", "diagnose", "therapie", "arzt", "medizin", "symptom"],
    "employment": ["kündigung", "gehalt", "abmahnung", "arbeitsvertrag", "bewerbung", "lebenslauf"],
    "legal": ["klage", "vertrag", "anwalt", "gericht", "straf", "mahnung"],
}

BUSINESS_CONFIDENTIAL_KEYWORDS = [
    "vertraulich",
    "nda",
    "kundendaten",
    "kundenliste",
    "umsatzplanung",
    "strategie",
    "board deck",
    "internes memo",
]

TASK_PATTERNS: list[tuple[str, list[str]]] = [
    ("format_table", ["tabelle", "csv", "spalte", "zeile", "tabellarisch"]),
    ("extract_entities", ["extrahiere", "finde alle", "entities", "e-mail-adressen", "telefonnummern"]),
    ("summarize", ["fasse", "zusammenfassung", "summarize", "tl;dr"]),
    ("rewrite", ["formuliere", "umschreiben", "rewrite", "professioneller", "kürzer"]),
    ("write_email", ["schreibe eine mail", "schreibe eine e-mail", "email an", "antwort an"]),
    ("classify", ["klassifiziere", "ordne ein", "kategorisiere"]),
    ("code", ["python", "javascript", "typescript", "sql", "bug", "funktion", "klasse", "code"]),
    ("agentic_task", ["buche", "plane", "recherchiere", "überwache", "sende", "termin"]),
]

SIMPLE_TASKS = {"format_table", "extract_entities", "rewrite"}


def classify_task(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for task_type, markers in TASK_PATTERNS:
        if any(marker in lowered for marker in markers):
            complexity = "low" if task_type in SIMPLE_TASKS else "medium"
            return task_type, complexity
    return "unknown", "medium"


def classify_prompt(text: str) -> ClassificationResult:
    redaction = redact(text)
    reason_codes = {entity.reason_code for entity in redaction.entities}
    pii_types = sorted({entity.type for entity in redaction.entities if entity.type in {"PERSON", "EMAIL", "PHONE", "IBAN"}})
    contains_secrets = any(entity.type in {"API_KEY", "PRIVATE_KEY"} for entity in redaction.entities)
    contains_pii = bool(pii_types)

    lowered = text.lower()
    sensitive_context_matches: list[str] = []
    for context, keywords in SENSITIVE_CONTEXT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            sensitive_context_matches.append(context)
            reason_codes.add(f"SENSITIVE_{context.upper()}_KEYWORD")

    business_confidential = any(keyword in lowered for keyword in BUSINESS_CONFIDENTIAL_KEYWORDS)
    if business_confidential:
        reason_codes.add("BUSINESS_CONFIDENTIAL_KEYWORD")

    task_type, complexity = classify_task(text)

    if contains_secrets:
        sensitivity = "credentials"
        confidence = 0.99
    elif contains_pii:
        sensitivity = "personal_data"
        confidence = 0.95 if any(code.endswith("PATTERN") for code in reason_codes) else 0.85
    elif sensitive_context_matches:
        sensitivity = "sensitive_context"
        confidence = 0.82
    elif business_confidential:
        sensitivity = "business_confidential"
        confidence = 0.84
    else:
        sensitivity = "public"
        confidence = 0.92
        reason_codes.add("NO_SENSITIVE_SIGNAL")

    # A tiny ambiguity guard: very short unknown prompts are less trustworthy.
    if sensitivity == "public" and task_type == "unknown" and len(re.findall(r"\w+", text)) < 4:
        sensitivity = "ambiguous"
        confidence = 0.55
        reason_codes.discard("NO_SENSITIVE_SIGNAL")
        reason_codes.add("LOW_INFORMATION_PROMPT")

    return ClassificationResult(
        sensitivity=sensitivity,
        contains_pii=contains_pii,
        contains_secrets=contains_secrets,
        business_confidential=business_confidential,
        pii_types=pii_types,
        task_type=task_type,
        complexity=complexity,
        confidence=confidence,
        reason_codes=sorted(reason_codes),
        redacted_prompt=redaction.redacted_text,
    )
