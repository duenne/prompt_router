from __future__ import annotations

import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "prompt_router_eval_v0_1.schema.json"
EVAL_DATASET_DIR = Path(__file__).resolve().parents[1] / "datasets/eval"
DEV_BATCH_PATH = EVAL_DATASET_DIR / "prompt_router_eval_v0_1_dev_batch_001.jsonl"
PAPER_INSPIRED_BATCH_PATH = (
    EVAL_DATASET_DIR / "prompt_router_eval_v0_1_paper_inspired_batch_002.jsonl"
)
EXPECTED_DATASET_PATHS = {DEV_BATCH_PATH, PAPER_INSPIRED_BATCH_PATH}

SENSITIVITY_IDS = {
    "public": 0,
    "personal_data": 1,
    "sensitive_context": 2,
    "business_confidential": 3,
    "credentials": 4,
    "ambiguous": 5,
}
TASK_TYPE_IDS = {
    "format_table": 0,
    "extract_entities": 1,
    "summarize": 2,
    "rewrite": 3,
    "write_email": 4,
    "classify": 5,
    "code": 6,
    "agentic_task": 7,
    "unknown": 8,
}
COMPLEXITY_IDS = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
ROUTE_IDS = {
    "block_or_internal_security": 0,
    "internal_llm": 1,
    "internal_small_model": 2,
    "specialized_executor": 3,
    "external_llm": 4,
    "internal_and_review": 5,
}
RISK_BITS = {
    "has_pii": 1,
    "has_secrets": 2,
    "has_sensitive_context": 4,
    "has_business_confidential": 8,
    "has_prompt_injection": 16,
    "is_ambiguous": 32,
}
POLICY_BITS = {
    "must_not_route_external": 1,
    "must_block_or_security": 2,
    "must_review": 4,
    "must_use_specialized_executor": 8,
    "may_route_external": 16,
}


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records = []
    with path.open(encoding="utf-8") as dataset_file:
        for line_number, line in enumerate(dataset_file, 1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise AssertionError(
                    f"{path}:{line_number} is not valid JSON: {error.msg}"
                ) from error
    return records


class EvalDatasetSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
            cls.schema = json.load(schema_file)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def public_example(self) -> dict[str, object]:
        return {
            "schema_version": "prompt_router_eval_v0_1",
            "id": "eval-public-001",
            "prompt": "Summarize this public announcement.",
            "language": "en",
            "source_type": "synthetic",
            "sensitivity_label": "public",
            "task_type_label": "summarize",
            "complexity_label": "low",
            "domain_label": "general",
            "expected_route": "external_llm",
            "expected_allowed_external": True,
            "expected_reason_codes": ["PUBLIC_EXTERNAL_ALLOWED"],
            "requires_review": False,
            "contains_prompt_injection": False,
            "policy_expectation": "may_route_external",
            "split": "test",
            "notes": "Minimal public synthetic example.",
            "risk_flags": {
                "has_pii": False,
                "has_secrets": False,
                "has_sensitive_context": False,
                "has_business_confidential": False,
                "has_prompt_injection": False,
                "is_ambiguous": False,
            },
            "routing_vector": {
                "schema_version": "0.1",
                "sensitivity_id": 0,
                "task_type_id": 2,
                "complexity_id": 0,
                "route_id": 4,
                "risk_bits": 0,
                "policy_bits": 16,
            },
            "persona": {
                "persona_id": "public-general-en",
                "role": "member_of_public",
                "domain": "general",
                "language_style": "plain",
                "expertise_level": "general",
                "risk_posture": "neutral",
            },
            "generation_metadata": {
                "generation_method": "template",
                "template_id": "public-summary-v1",
                "generator": "fixture",
                "review_status": "reviewed",
                "synthetic_data_only": True,
            },
        }

    def assert_valid(self, instance: dict[str, object]) -> None:
        self.validator.validate(instance)

    def assert_invalid(self, instance: dict[str, object]) -> None:
        with self.assertRaises(ValidationError):
            self.validator.validate(instance)

    def test_valid_minimal_public_example(self) -> None:
        self.assert_valid(self.public_example())

    def test_valid_dev_split(self) -> None:
        example = self.public_example()
        example["split"] = "dev"

        self.assert_valid(example)

    def test_valid_test_split(self) -> None:
        example = self.public_example()
        example["split"] = "test"

        self.assert_valid(example)

    def test_valid_challenge_split(self) -> None:
        example = self.public_example()
        example["split"] = "challenge"

        self.assert_valid(example)

    def test_invalid_train_split(self) -> None:
        example = self.public_example()
        example["split"] = "train"

        self.assert_invalid(example)

    def test_valid_pii_example(self) -> None:
        example = self.public_example()
        example.update(
            sensitivity_label="personal_data",
            expected_route="internal_small_model",
            expected_allowed_external=False,
            policy_expectation="must_not_route_external",
        )
        example["risk_flags"]["has_pii"] = True
        example["routing_vector"].update(
            sensitivity_id=1, route_id=2, risk_bits=1, policy_bits=1
        )

        self.assert_valid(example)

    def test_valid_credentials_example(self) -> None:
        example = self.public_example()
        example.update(
            sensitivity_label="credentials",
            expected_route="block_or_internal_security",
            expected_allowed_external=False,
            policy_expectation="must_block_or_security",
        )
        example["risk_flags"]["has_secrets"] = True
        example["routing_vector"].update(
            sensitivity_id=4, route_id=0, risk_bits=2, policy_bits=3
        )

        self.assert_valid(example)

    def test_invalid_credentials_example_routed_externally(self) -> None:
        example = self.public_example()
        example.update(sensitivity_label="credentials")
        example["risk_flags"]["has_secrets"] = True
        example["routing_vector"].update(sensitivity_id=4, risk_bits=2)

        self.assert_invalid(example)

    def test_invalid_non_public_example_allows_external(self) -> None:
        example = self.public_example()
        example.update(sensitivity_label="personal_data")
        example["risk_flags"]["has_pii"] = True
        example["routing_vector"].update(sensitivity_id=1, risk_bits=1)

        self.assert_invalid(example)

    def test_invalid_prompt_injection_flag_mismatch(self) -> None:
        example = copy.deepcopy(self.public_example())
        example["contains_prompt_injection"] = True

        self.assert_invalid(example)


class EvalDevBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
        cls.validator = Draft202012Validator(schema)
        cls.records = load_jsonl(DEV_BATCH_PATH)

    def test_every_row_validates_and_ids_are_sequential(self) -> None:
        self.assertEqual(len(self.records), 40)
        self.assertEqual(
            [record["id"] for record in self.records],
            [f"eval_dev_{number:06d}" for number in range(1, 41)],
        )
        for record in self.records:
            with self.subTest(record_id=record["id"]):
                self.validator.validate(record)
                self.assertEqual(record["schema_version"], "prompt_router_eval_v0_1")
                self.assertEqual(record["source_type"], "synthetic")
                self.assertEqual(record["split"], "dev")

    def test_target_distribution(self) -> None:
        ordinary = [
            record for record in self.records if not record["contains_prompt_injection"]
        ]
        expected_ordinary_sensitivity = {
            "public": 12,
            "personal_data": 7,
            "credentials": 5,
            "sensitive_context": 5,
            "business_confidential": 5,
            "ambiguous": 3,
        }
        self.assertEqual(len(ordinary), 37)
        for label, expected_count in expected_ordinary_sensitivity.items():
            self.assertEqual(
                sum(record["sensitivity_label"] == label for record in ordinary),
                expected_count,
            )
        self.assertEqual(
            sum(
                record["sensitivity_label"] == "public"
                and record["expected_route"] == "specialized_executor"
                for record in ordinary
            ),
            6,
        )
        self.assertEqual(
            sum(
                record["sensitivity_label"] == "public"
                and record["expected_route"] == "external_llm"
                for record in ordinary
            ),
            6,
        )
        self.assertEqual(
            sum(record["contains_prompt_injection"] for record in self.records), 3
        )
        self.assertEqual(
            {language: sum(r["language"] == language for r in self.records)
             for language in ("de", "en", "mixed")},
            {"de": 20, "en": 15, "mixed": 5},
        )

    def test_all_persona_archetypes_are_present(self) -> None:
        required_personas = {
            "busy_founder",
            "software_developer",
            "hr_manager",
            "finance_analyst",
            "medical_patient",
            "legal_assistant",
            "student",
            "security_engineer",
            "automation_agent",
            "adversarial_user",
        }
        self.assertTrue(
            required_personas.issubset(
                {record["persona"]["persona_id"] for record in self.records}
            )
        )

    def test_policy_and_routing_vectors_are_consistent(self) -> None:
        for record in self.records:
            with self.subTest(record_id=record["id"]):
                flags = record["risk_flags"]
                vector = record["routing_vector"]
                if record["sensitivity_label"] != "public":
                    self.assertFalse(record["expected_allowed_external"])
                if record["sensitivity_label"] == "credentials":
                    self.assertEqual(
                        record["expected_route"], "block_or_internal_security"
                    )
                if record["contains_prompt_injection"]:
                    self.assertTrue(flags["has_prompt_injection"])
                    self.assertIn(
                        "PROMPT_INJECTION_ATTEMPT",
                        record["expected_reason_codes"],
                    )
                self.assertEqual(
                    vector["sensitivity_id"],
                    SENSITIVITY_IDS[record["sensitivity_label"]],
                )
                self.assertEqual(
                    vector["task_type_id"], TASK_TYPE_IDS[record["task_type_label"]]
                )
                self.assertEqual(
                    vector["complexity_id"],
                    COMPLEXITY_IDS[record["complexity_label"]],
                )
                self.assertEqual(
                    vector["route_id"], ROUTE_IDS[record["expected_route"]]
                )
                self.assertEqual(
                    vector["risk_bits"],
                    sum(bit for flag, bit in RISK_BITS.items() if flags[flag]),
                )
                self.assertEqual(
                    vector["policy_bits"], POLICY_BITS[record["policy_expectation"]]
                )


class EvalAllDatasetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
        cls.validator = Draft202012Validator(schema)
        cls.dataset_paths = sorted(EVAL_DATASET_DIR.glob("*.jsonl"))
        cls.records_by_path = {
            path: load_jsonl(path) for path in cls.dataset_paths
        }
        cls.records = [
            record
            for records in cls.records_by_path.values()
            for record in records
        ]

    def test_expected_batches_and_all_eval_jsonl_files_are_loaded(self) -> None:
        self.assertTrue(EXPECTED_DATASET_PATHS.issubset(self.dataset_paths))
        self.assertEqual(set(self.dataset_paths), set(self.records_by_path))

    def test_every_record_validates_against_schema(self) -> None:
        for path, records in self.records_by_path.items():
            for line_number, record in enumerate(records, 1):
                with self.subTest(path=path.name, line=line_number):
                    self.validator.validate(record)

    def test_ids_are_unique_across_all_eval_jsonl_files(self) -> None:
        ids = [record["id"] for record in self.records]
        self.assertEqual(len(ids), len(set(ids)))

    def test_policy_flags_and_vectors_are_consistent_across_all_files(self) -> None:
        for record in self.records:
            with self.subTest(record_id=record["id"]):
                flags = record["risk_flags"]
                vector = record["routing_vector"]
                if record["sensitivity_label"] != "public":
                    self.assertFalse(record["expected_allowed_external"])
                if record["sensitivity_label"] == "credentials":
                    self.assertEqual(
                        record["expected_route"], "block_or_internal_security"
                    )
                if record["contains_prompt_injection"]:
                    self.assertTrue(flags["has_prompt_injection"])
                    self.assertIn(
                        "PROMPT_INJECTION_ATTEMPT",
                        record["expected_reason_codes"],
                    )
                self.assertEqual(
                    vector["sensitivity_id"],
                    SENSITIVITY_IDS[record["sensitivity_label"]],
                )
                self.assertEqual(
                    vector["task_type_id"], TASK_TYPE_IDS[record["task_type_label"]]
                )
                self.assertEqual(
                    vector["complexity_id"],
                    COMPLEXITY_IDS[record["complexity_label"]],
                )
                self.assertEqual(
                    vector["route_id"], ROUTE_IDS[record["expected_route"]]
                )
                self.assertEqual(
                    vector["risk_bits"],
                    sum(bit for flag, bit in RISK_BITS.items() if flags[flag]),
                )
                self.assertEqual(
                    vector["policy_bits"], POLICY_BITS[record["policy_expectation"]]
                )

    def test_distribution_summaries_cover_every_record(self) -> None:
        summaries = {
            field: Counter(record[field] for record in self.records)
            for field in (
                "split",
                "sensitivity_label",
                "expected_route",
                "task_type_label",
            )
        }
        for field, summary in summaries.items():
            with self.subTest(field=field):
                self.assertEqual(sum(summary.values()), len(self.records))


if __name__ == "__main__":
    unittest.main()
