from __future__ import annotations

import unittest

from prompt_router.classifier import classify_prompt
from prompt_router.policy import decide_route
from prompt_router.redactor import redact
from prompt_router.schemas import ClassificationResult


class ClassifierPolicyTests(unittest.TestCase):
    def classification(self, **overrides: object) -> ClassificationResult:
        values: dict[str, object] = {
            "sensitivity": "public",
            "contains_pii": False,
            "contains_secrets": False,
            "business_confidential": False,
            "pii_types": [],
            "task_type": "summarize",
            "complexity": "medium",
            "confidence": 0.95,
            "reason_codes": [],
            "redacted_prompt": "redacted",
        }
        values.update(overrides)
        return ClassificationResult(**values)  # type: ignore[arg-type]

    def test_email_and_phone_route_internal_small_model_for_table_task(self) -> None:
        result = classify_prompt("Mach daraus eine Tabelle: Max Müller, max@example.com, 0176 123456")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "personal_data")
        self.assertIn("EMAIL", result.pii_types)
        self.assertEqual(result.task_type, "format_table")
        self.assertEqual(decision.route, "internal_small_model")
        self.assertFalse(decision.allowed_external)

    def test_public_summary_can_route_external(self) -> None:
        result = classify_prompt("Fasse diesen öffentlichen Produkttext zusammen")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "public")
        self.assertEqual(result.task_type, "summarize")
        self.assertEqual(decision.route, "external_llm")
        self.assertTrue(decision.allowed_external)

    def test_sensitive_health_context_routes_internal_review(self) -> None:
        result = classify_prompt("Bitte fasse den Krankheitsverlauf dieser Patientin zusammen")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "sensitive_context")
        self.assertEqual(decision.route, "internal_llm")
        self.assertTrue(decision.should_review)

    def test_business_confidential_routes_internal_review(self) -> None:
        result = classify_prompt("Fasse dieses vertrauliche interne Memo zusammen")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "business_confidential")
        self.assertEqual(decision.route, "internal_llm")
        self.assertFalse(decision.allowed_external)
        self.assertTrue(decision.should_review)
        self.assertEqual(decision.review_reason, "business_confidential")

    def test_personal_data_non_simple_task_uses_internal_llm(self) -> None:
        result = classify_prompt("Fasse den Text für Max Müller zusammen")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "personal_data")
        self.assertEqual(result.task_type, "summarize")
        self.assertEqual(decision.route, "internal_llm")
        self.assertFalse(decision.should_review)

    def test_ambiguous_prompt_routes_internal_review(self) -> None:
        result = classify_prompt("Bitte prüfen")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "ambiguous")
        self.assertEqual(decision.route, "internal_and_review")
        self.assertFalse(decision.allowed_external)
        self.assertTrue(decision.should_review)
        self.assertEqual(decision.review_reason, "low_confidence")

    def test_public_low_confidence_routes_internal_review(self) -> None:
        result = self.classification(confidence=0.80)
        decision = decide_route(result, confidence_threshold=0.90)
        self.assertEqual(decision.route, "internal_and_review")
        self.assertTrue(decision.should_review)
        self.assertIn("LOW_CONFIDENCE", decision.reason_codes)

    def test_public_simple_task_uses_specialized_executor(self) -> None:
        result = classify_prompt("Extrahiere die Überschriften aus diesem öffentlichen Text")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "public")
        self.assertEqual(result.task_type, "extract_entities")
        self.assertEqual(decision.route, "specialized_executor")
        self.assertFalse(decision.allowed_external)
        self.assertFalse(decision.should_review)

    def test_secret_blocks_or_security(self) -> None:
        result = classify_prompt("Hier ist mein API Key: sk-abcdefghijklmnopqrstuvwxyz")
        decision = decide_route(result)
        self.assertEqual(result.sensitivity, "credentials")
        self.assertEqual(decision.route, "block_or_internal_security")
        self.assertFalse(decision.allowed_external)

    def test_secret_signal_takes_precedence_over_personal_data(self) -> None:
        result = self.classification(
            sensitivity="personal_data",
            contains_pii=True,
            contains_secrets=True,
            pii_types=["EMAIL"],
            task_type="format_table",
        )
        decision = decide_route(result)
        self.assertEqual(decision.route, "block_or_internal_security")
        self.assertTrue(decision.should_review)
        self.assertEqual(decision.review_reason, "secret_detected")

    def test_redaction_replaces_entities(self) -> None:
        result = redact("Schreibe an Max Müller unter max@example.com")
        self.assertIn("[PERSON_1]", result.redacted_text)
        self.assertIn("[EMAIL_1]", result.redacted_text)


if __name__ == "__main__":
    unittest.main()
