from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from prompt_router.evaluator import evaluate_dataset


ROOT = Path(__file__).resolve().parents[1]
DEV_DATASET = ROOT / "datasets/eval/prompt_router_eval_v0_1_dev_batch_001.jsonl"
PAPER_DATASET = (
    ROOT / "datasets/eval/prompt_router_eval_v0_1_paper_inspired_batch_002.jsonl"
)
HARDENING_DATASET = (
    ROOT / "datasets/eval/prompt_router_eval_v0_1_hardening_batch_003.jsonl"
)

SENSITIVITY_IDS = {
    "public": 0,
    "personal_data": 1,
    "sensitive_context": 2,
    "business_confidential": 3,
    "credentials": 4,
    "ambiguous": 5,
}
TASK_IDS = {
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
ROUTE_IDS = {
    "block_or_internal_security": 0,
    "internal_llm": 1,
    "internal_small_model": 2,
    "specialized_executor": 3,
    "external_llm": 4,
    "internal_and_review": 5,
}
POLICY_BITS = {
    "must_not_route_external": 1,
    "must_block_or_security": 2,
    "must_review": 4,
    "must_use_specialized_executor": 8,
    "may_route_external": 16,
}


def base_record() -> dict[str, object]:
    with DEV_DATASET.open(encoding="utf-8") as dataset_file:
        return json.loads(next(dataset_file))


def record(
    record_id: str,
    prompt: str,
    *,
    sensitivity: str = "public",
    task_type: str = "summarize",
    route: str = "external_llm",
    allowed_external: bool = True,
    requires_review: bool = False,
    expected_reason_codes: list[str] | None = None,
    policy_expectation: str = "may_route_external",
    has_pii: bool = False,
    has_secrets: bool = False,
) -> dict[str, object]:
    value = copy.deepcopy(base_record())
    value.update(
        id=record_id,
        prompt=prompt,
        sensitivity_label=sensitivity,
        task_type_label=task_type,
        expected_route=route,
        expected_allowed_external=allowed_external,
        requires_review=requires_review,
        expected_reason_codes=expected_reason_codes or [],
        policy_expectation=policy_expectation,
    )
    value["risk_flags"].update(
        has_pii=has_pii,
        has_secrets=has_secrets,
        has_sensitive_context=sensitivity == "sensitive_context",
        has_business_confidential=sensitivity == "business_confidential",
        has_prompt_injection=False,
        is_ambiguous=sensitivity == "ambiguous",
    )
    risk_bits = (
        int(has_pii)
        + 2 * int(has_secrets)
        + 4 * int(sensitivity == "sensitive_context")
        + 8 * int(sensitivity == "business_confidential")
        + 32 * int(sensitivity == "ambiguous")
    )
    value["routing_vector"].update(
        sensitivity_id=SENSITIVITY_IDS[sensitivity],
        task_type_id=TASK_IDS[task_type],
        route_id=ROUTE_IDS[route],
        risk_bits=risk_bits,
        policy_bits=POLICY_BITS[policy_expectation],
    )
    return value


class EvalTests(unittest.TestCase):
    def run_pr(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for name in (
            "PROMPT_ROUTER_CONFIG",
            "PROMPT_ROUTER_DB",
            "PROMPT_ROUTER_DEFAULT_SHARING_LEVEL",
            "PROMPT_ROUTER_CONFIDENCE_THRESHOLD",
        ):
            env.pop(name, None)
        return subprocess.run(
            [sys.executable, "-m", "prompt_router", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_status_does_not_import_eval_dependencies(self) -> None:
        script = """
import builtins
real_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'jsonschema' or name.startswith('jsonschema.'):
        raise ModuleNotFoundError('blocked jsonschema import')
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
from prompt_router.cli import main
raise SystemExit(main(['status']))
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "local_first")

    def write_dataset(
        self, directory: str, records: list[dict[str, object]]
    ) -> Path:
        path = Path(directory) / "fixture.jsonl"
        path.write_text(
            "".join(json.dumps(item) + "\n" for item in records),
            encoding="utf-8",
        )
        return path

    def test_eval_cli_works_on_tiny_valid_fixture(self) -> None:
        item = record(
            "eval-test-1",
            "fasse diesen öffentlichen text zusammen",
            expected_reason_codes=["NO_SENSITIVE_SIGNAL", "PUBLIC_EXTERNAL_ALLOWED"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_dataset(tmpdir, [item])
            result = self.run_pr("eval", "--dataset", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Total records: 1", result.stdout)
        self.assertIn("Route accuracy: 1.0000", result.stdout)

    def test_eval_cli_json_returns_parseable_json(self) -> None:
        item = record("eval-test-1", "fasse diesen öffentlichen text zusammen")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_dataset(tmpdir, [item])
            result = self.run_pr("eval", "--dataset", str(path), "--json")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["total_records"], 1)
        self.assertIn("route_accuracy", payload["metrics"])

    def test_invalid_jsonl_line_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.jsonl"
            path.write_text("{not json}\n", encoding="utf-8")
            result = self.run_pr("eval", "--dataset", str(path))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("line 1 is not valid JSON", result.stdout)

    def test_missing_dataset_fails_clearly(self) -> None:
        result = self.run_pr("eval", "--dataset", "does-not-exist.jsonl")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dataset file does not exist", result.stdout)

    def test_schema_invalid_record_fails_clearly(self) -> None:
        item = record("eval-test-1", "fasse diesen öffentlichen text zusammen")
        del item["prompt"]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_dataset(tmpdir, [item])
            result = self.run_pr("eval", "--dataset", str(path))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("line 1 does not validate", result.stdout)
        self.assertIn("prompt", result.stdout)

    def test_false_external_rate_uses_expected_internal_denominator(self) -> None:
        unsafe = record(
            "eval-test-1",
            "fasse diesen öffentlichen text zusammen",
            task_type="format_table",
            route="specialized_executor",
            allowed_external=False,
            policy_expectation="must_use_specialized_executor",
        )
        safe = record(
            "eval-test-2",
            "erstelle eine tabelle aus rot und blau",
            task_type="format_table",
            route="specialized_executor",
            allowed_external=False,
            policy_expectation="must_use_specialized_executor",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_dataset(tmpdir, [unsafe, safe])
            result = evaluate_dataset(path)
            metrics = result["metrics"]

        self.assertEqual(metrics["false_external_count"], 1)
        self.assertEqual(metrics["false_external_rate"], 0.5)
        self.assertEqual(len(result["false_external_failures"]), 1)
        self.assertEqual(len(result["safety_critical_failures"]), 1)

    def test_reason_code_exact_and_partial_match_rates(self) -> None:
        prompt = "fasse diesen öffentlichen text zusammen"
        exact = record(
            "eval-test-1",
            prompt,
            expected_reason_codes=["NO_SENSITIVE_SIGNAL", "PUBLIC_EXTERNAL_ALLOWED"],
        )
        partial = record(
            "eval-test-2",
            prompt,
            expected_reason_codes=["PUBLIC_EXTERNAL_ALLOWED", "EXPECTED_EXTRA"],
        )
        disjoint = record(
            "eval-test-3", prompt, expected_reason_codes=["EXPECTED_ONLY"]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_dataset(tmpdir, [exact, partial, disjoint])
            metrics = evaluate_dataset(path)["metrics"]

        self.assertAlmostEqual(metrics["reason_code_exact_match_rate"], 1 / 3)
        self.assertAlmostEqual(metrics["reason_code_partial_match_rate"], 2 / 3)
        self.assertAlmostEqual(metrics["expected_reason_code_recall"], 3 / 5)

    def test_secret_and_pii_recall(self) -> None:
        detected_secret = record(
            "eval-test-1",
            "prüfe api_ABCDEFGHIJKLMNOPQRST",
            sensitivity="credentials",
            task_type="unknown",
            route="block_or_internal_security",
            allowed_external=False,
            policy_expectation="must_block_or_security",
            has_secrets=True,
        )
        missed_secret = record(
            "eval-test-2",
            "fasse diesen öffentlichen text zusammen",
            sensitivity="credentials",
            task_type="unknown",
            route="block_or_internal_security",
            allowed_external=False,
            policy_expectation="must_block_or_security",
            has_secrets=True,
        )
        detected_pii = record(
            "eval-test-3",
            "schreibe an Max Müller unter max@example.test",
            sensitivity="personal_data",
            task_type="write_email",
            route="internal_llm",
            allowed_external=False,
            policy_expectation="must_not_route_external",
            has_pii=True,
        )
        missed_pii = record(
            "eval-test-4",
            "fasse diesen öffentlichen text zusammen",
            sensitivity="personal_data",
            task_type="summarize",
            route="internal_llm",
            allowed_external=False,
            policy_expectation="must_not_route_external",
            has_pii=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_dataset(
                tmpdir, [detected_secret, missed_secret, detected_pii, missed_pii]
            )
            metrics = evaluate_dataset(path)["metrics"]

        self.assertEqual(metrics["secret_total"], 2)
        self.assertEqual(metrics["secret_recall"], 0.5)
        self.assertEqual(metrics["pii_total"], 2)
        self.assertEqual(metrics["pii_recall"], 0.5)

    def test_existing_datasets_validate_and_can_be_evaluated(self) -> None:
        for path, expected_total in (
            (DEV_DATASET, 40),
            (PAPER_DATASET, 60),
            (HARDENING_DATASET, 50),
        ):
            with self.subTest(path=path.name):
                result = self.run_pr(
                    "eval", "--dataset", str(path.relative_to(ROOT)), "--json"
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["total_records"], expected_total)
                self.assertEqual(payload["metrics"]["false_external_count"], 0)


if __name__ == "__main__":
    unittest.main()
