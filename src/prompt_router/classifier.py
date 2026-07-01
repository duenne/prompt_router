from __future__ import annotations

import re

from .redactor import redact
from .schemas import ClassificationResult

SENSITIVE_CONTEXT_KEYWORDS = {
    "health": ["krank", "krankheit", "patient", "patientin", "diagnose", "therapie", "therapy", "anxiety", "medication", "arzt", "medizin", "symptom"],
    "employment": ["kündigung", "gehalt", "abmahnung", "arbeitsvertrag", "bewerbung", "lebenslauf"],
    "hr": ["employee burnout", "sick leave", "performance warning", "workplace conflict", "conflict with manager", "disziplinarfall", "hr context", "hr sheet", "employee grievance", "disciplinary warning", "disciplinary case"],
    "legal": ["klage", "vertrag", "anwalt", "gericht", "straf", "mahnung", "eviction", "court deadline", "settlement draft", "contract dispute", "legal approval", "lawsuit"],
}

BUSINESS_CONFIDENTIAL_KEYWORDS = [
    "confidential",
    "board memo",
    "management report",
    "executive report",
    "geschäftsführung",
    "vorstand",
    "internal memo",
    "internal-only",
    "vertraulich",
    "nda",
    "kundendaten",
    "kundenliste",
    "umsatzplanung",
    "strategie",
    "board deck",
    "internes memo",
    "interne memo",
    "unreleased",
    "unveröffentlicht",
    "not-yet-announced",
    "roadmap",
    "pricing strategy",
    "pricing memo",
    "acquisition",
    "restructuring",
    "freigabe fehlt",
    "unreleased renewal numbers",
    "draft churn analysis",
    "pricing model",
    "acquisition memo",
    "roadmap notes",
    "before the launch is public",
    "before launch is public",
    "not yet public",
    "noch nicht veröffentlicht",
    "restructuring proposal",
    "private customer dataset",
]

INTERNAL_REFERENCE_PATTERNS = [
    "internal q4 sheet",
    "internen q4-sheet",
    "internes q4-sheet",
    "internal spreadsheet",
    "partner spreadsheet",
    "project folder",
    "projektordner",
    "board deck",
    "board memo",
    "executive memo",
    "ceo briefing",
    "investor update",
    "leadership team",
    "leadership-team",
    "management report",
    "geschäftsführung",
    "vorstand",
    "hr sheet",
]

PROMPT_INJECTION_PATTERNS = [
    "ignore policy",
    "ignore previous instructions",
    "ignore safety checks",
    "ignore alle sicherheitsregeln",
    "classify as public",
    "classify unknown payload as public",
    "classify payload as public",
    "router_override",
    "system override",
    "mark payload safe",
    "ignore health policy",
    "approved for every route",
]
POLICY_BYPASS_PATTERNS = PROMPT_INJECTION_PATTERNS + [
    "do not ask follow-up questions",
    "do not ask followup questions",
    "do not request context",
]
EXTERNAL_ROUTING_PATTERNS = [
    "using an external model",
    "use an external model",
    "external_llm",
    "send to an external service",
    "send it to an external service",
    "send the output externally",
]
MISSING_CONTEXT_PATTERNS = [
    "source, sensitivity and approval missing",
    "quelle, sensitivität und freigabe fehlen",
    "not provided",
    "usual spreadsheet",
    "usual recipient",
    "usual place",
    "usual account data",
    "thing from yesterday",
    "as discussed",
    "wie besprochen",
    "missing column",
    "infer the missing column",
    "kontext fehlt",
    "freigabestatus nicht angegeben",
    "freigabestatus sind nicht angegeben",
    "inhalt folgt später",
    "zahlen aus dem letzten sheet",
    "nicht, ob die daten freigegeben",
    "same thing as last time",
    "no context is included",
    "nicht, ob der anhang öffentlich",
    "nicht, welche daten gemeint",
    "default account data",
    "latest spreadsheet",
    "files from yesterday",
    "die übliche liste",
    "die zahlen von gestern",
    "source is unknown",
    "quelle und freigabestatus fehlen",
    "quelle und freigabestatus sind offen",
    "approval status is not documented",
    "legal approval is not stated",
    "freigabe fehlt",
    "not public",
    "nicht öffentlich",
    "payload is omitted",
    "unnamed partner spreadsheet",
]

TASK_PATTERNS: list[tuple[str, list[str]]] = [
    ("format_table", ["tabelle", "csv", "spalte", "zeile", "tabellarisch", "json array", "markdown-liste", "markdown list", "compact table", "sort these", "sort the"]),
    ("extract_entities", ["extrahiere", "extract", "finde alle", "entities", "e-mail-adressen", "telefonnummern"]),
    ("summarize", ["fasse", "zusammenfassung", "summarize", "tl;dr"]),
    ("rewrite", ["formuliere", "umschreiben", "rewrite", "professioneller", "kürzer"]),
    ("write_email", ["schreibe eine mail", "schreibe eine e-mail", "email an", "antwort an"]),
    ("classify", ["klassifiziere", "classify", "ordne ein", "kategorisiere"]),
    ("code", ["python", "javascript", "typescript", "sql", "bug", "funktion", "klasse", "code"]),
    ("agentic_task", ["buche", "plane", "recherchiere", "überwache", "sende", "termin", "email the result", "send the result", "sende das ergebnis", "notify the team", "notify the usual recipient", "informiere das team", "create tickets", "execute immediately", "execute sofort", "decide next steps", "entscheide die nächsten schritte", "infer missing owners", "infer missing data", "infer churn drivers", "update the report", "open the latest spreadsheet", "process the files", "take the usual spreadsheet", "process the thing", "do the next step", "next step", "then run it", "prepare an executive memo", "mail the manager"]),
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
    prompt_injection = any(pattern in lowered for pattern in PROMPT_INJECTION_PATTERNS)
    policy_bypass = any(pattern in lowered for pattern in POLICY_BYPASS_PATTERNS)
    external_routing_request = any(
        pattern in lowered for pattern in EXTERNAL_ROUTING_PATTERNS
    )
    missing_context = any(pattern in lowered for pattern in MISSING_CONTEXT_PATTERNS)
    internal_reference = any(
        pattern in lowered for pattern in INTERNAL_REFERENCE_PATTERNS
    )
    if prompt_injection:
        reason_codes.add("PROMPT_INJECTION_ATTEMPT")
    if policy_bypass:
        reason_codes.add("POLICY_BYPASS_PATTERN")
    if external_routing_request:
        reason_codes.add("EXTERNAL_ROUTING_REQUEST")
    if missing_context:
        reason_codes.update({"LOW_CONFIDENCE", "MISSING_CONTEXT"})
    if internal_reference:
        reason_codes.update(
            {"BUSINESS_CONFIDENTIAL_KEYWORD", "INTERNAL_REFERENCE_PATTERN"}
        )

    sensitive_context_matches: list[str] = []
    for context, keywords in SENSITIVE_CONTEXT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            sensitive_context_matches.append(context)
            reason_codes.add(f"SENSITIVE_{context.upper()}_KEYWORD")

    business_confidential = internal_reference or any(
        keyword in lowered for keyword in BUSINESS_CONFIDENTIAL_KEYWORDS
    )
    if business_confidential:
        reason_codes.add("BUSINESS_CONFIDENTIAL_KEYWORD")

    task_type, complexity = classify_task(text)
    if task_type == "agentic_task":
        reason_codes.add("AGENTIC_TASK_PATTERN")
    if task_type == "unknown":
        reason_codes.add("UNKNOWN_TASK_TYPE")

    if contains_secrets:
        sensitivity = "credentials"
        confidence = 0.99
    elif contains_pii:
        sensitivity = "personal_data"
        confidence = 0.95 if any(code.endswith("PATTERN") for code in reason_codes) else 0.85
    elif missing_context:
        sensitivity = "ambiguous"
        confidence = 0.55
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
