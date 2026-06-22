from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from prompt_router.semantic import (
    SemanticConfigError,
    cosine_similarity,
    embed_text,
    load_prototypes,
    semantic_check,
)


class SemanticVectorTests(unittest.TestCase):
    def test_loads_required_prototype_labels(self) -> None:
        prototypes = load_prototypes()
        self.assertEqual(
            {prototype.label for prototype in prototypes},
            {"health", "employment", "public_table", "code", "credentials"},
        )
        self.assertTrue(all(prototype.text for prototype in prototypes))

    def test_embedding_is_deterministic_and_normalized(self) -> None:
        first = embed_text("Patientenakte und Behandlung")
        second = embed_text("Patientenakte und Behandlung")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 128)
        self.assertAlmostEqual(sum(value * value for value in first), 1.0)

    def test_cosine_similarity_is_bounded(self) -> None:
        left = embed_text("medizinische Behandlung")
        right = embed_text("medizinischer Verlauf")
        similarity = cosine_similarity(left, right)

        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)

    def test_rejects_invalid_prototype_json(self) -> None:
        invalid_documents = [
            {},
            [{"id": "health-1"}],
            [
                {
                    "id": "unknown-1",
                    "label": "unknown",
                    "text": "text",
                    "risk": True,
                    "sensitivity": "sensitive_context",
                }
            ],
        ]
        for document in invalid_documents:
            with self.subTest(document=document), tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "semantic.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(SemanticConfigError):
                    load_prototypes(path=path)


class SemanticCheckTests(unittest.TestCase):
    def test_health_context_matches_risk_prototype(self) -> None:
        result = semantic_check(
            "Fasse den medizinischen Verlauf und die Behandlung zusammen"
        )

        self.assertTrue(result.matched)
        self.assertTrue(result.risk_detected)
        self.assertEqual(result.label, "health")
        self.assertEqual(result.sensitivity, "sensitive_context")
        self.assertIn("SEMANTIC_HEALTH_RISK", result.reason_codes)

    def test_required_health_cli_phrase_matches_risk_prototype(self) -> None:
        result = semantic_check(
            "Bitte fasse den Krankheitsverlauf dieser Patientin zusammen"
        )

        self.assertTrue(result.risk_detected)
        self.assertEqual(result.label, "health")

    def test_health_paraphrase_without_deterministic_keywords_matches_risk(
        self,
    ) -> None:
        result = semantic_check(
            "befunde medikation und genesungsverlauf übersichtlich darstellen"
        )

        self.assertTrue(result.risk_detected)
        self.assertEqual(result.label, "health")

    def test_public_table_prompt_matches_without_risk(self) -> None:
        result = semantic_check(
            "Formatiere diese öffentlichen Informationen als Tabelle mit Spalten"
        )

        self.assertTrue(result.matched)
        self.assertFalse(result.risk_detected)
        self.assertEqual(result.label, "public_table")
        self.assertIsNone(result.sensitivity)
        self.assertNotIn("SEMANTIC_HEALTH_RISK", result.reason_codes)

    def test_unrelated_public_prompt_does_not_match_risk(self) -> None:
        result = semantic_check("Erkläre die Geschichte des Fahrrads")

        self.assertFalse(result.risk_detected)
        if not result.matched:
            self.assertEqual(result.reason_codes, ["SEMANTIC_NO_MATCH"])

    def test_result_contains_stable_model_metadata(self) -> None:
        result = semantic_check("Schreibe eine Python Funktion")

        self.assertEqual(result.model, "hashed-token-trigram")
        self.assertEqual(result.model_version, "1")
        self.assertGreater(result.threshold, 0.0)
        self.assertLessEqual(result.threshold, 1.0)


if __name__ == "__main__":
    unittest.main()
