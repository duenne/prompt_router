from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliDbTests(unittest.TestCase):
    def run_pr(
        self,
        *args: str,
        db_path: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        for name in (
            "PROMPT_ROUTER_CONFIG",
            "PROMPT_ROUTER_DB",
            "PROMPT_ROUTER_DEFAULT_SHARING_LEVEL",
            "PROMPT_ROUTER_CONFIDENCE_THRESHOLD",
        ):
            env.pop(name, None)
        if db_path is not None:
            env["PROMPT_ROUTER_DB"] = str(db_path)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-m", "prompt_router", *args],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_run_persists_event_without_raw_prompt_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "router.sqlite3"
            result = self.run_pr("run", "Schreibe an Max Müller unter max@example.com", db_path=db_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("event_id", payload)
            self.assertFalse(payload["raw_prompt_stored"])

            events = self.run_pr("events", "list", db_path=db_path)
            self.assertEqual(events.returncode, 0, events.stderr)
            rows = json.loads(events.stdout)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["route"], "internal_llm")

    def test_dry_run_does_not_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "router.sqlite3"
            result = self.run_pr("run", "Fasse den Text zusammen", "--dry-run", db_path=db_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertNotIn("event_id", payload)
            events = self.run_pr("events", "list", db_path=db_path)
            rows = json.loads(events.stdout)
            self.assertEqual(rows, [])

    def test_redact_outputs_structured_json_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pr(
                "redact",
                "Schreibe an Max Müller unter max@example.com",
                db_path=Path(tmpdir) / "router.sqlite3",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["redacted_text"],
            "Schreibe an [PERSON_1] unter [EMAIL_1]",
        )
        self.assertEqual(
            [entity["type"] for entity in payload["entities"]],
            ["PERSON", "EMAIL"],
        )

    def test_status_reports_file_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            database = Path(tmpdir) / "configured.sqlite3"
            config_path.write_text(
                json.dumps(
                    {
                        "database": str(database),
                        "default_sharing_level": "redacted",
                        "confidence_threshold": 0.95,
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_pr(
                "status",
                extra_env={"PROMPT_ROUTER_CONFIG": str(config_path)},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["database"], str(database))
        self.assertEqual(payload["default_sharing_level"], "redacted")
        self.assertEqual(payload["confidence_threshold"], 0.95)
        self.assertEqual(payload["config_file"], str(config_path))

    def test_run_uses_file_sharing_level_and_confidence_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            database = Path(tmpdir) / "configured.sqlite3"
            config_path.write_text(
                json.dumps(
                    {
                        "database": str(database),
                        "default_sharing_level": "redacted",
                        "confidence_threshold": 0.95,
                    }
                ),
                encoding="utf-8",
            )
            env = {"PROMPT_ROUTER_CONFIG": str(config_path)}

            result = self.run_pr(
                "run",
                "Fasse diesen öffentlichen Text zusammen",
                extra_env=env,
            )
            events = self.run_pr("events", "list", extra_env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["routing"]["route"], "internal_and_review")
        rows = json.loads(events.stdout)
        self.assertEqual(rows[0]["sharing_level"], "redacted")

    def test_environment_overrides_file_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            file_database = Path(tmpdir) / "file.sqlite3"
            env_database = Path(tmpdir) / "env.sqlite3"
            config_path.write_text(
                json.dumps(
                    {
                        "database": str(file_database),
                        "default_sharing_level": "redacted",
                        "confidence_threshold": 0.95,
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_pr(
                "status",
                extra_env={
                    "PROMPT_ROUTER_CONFIG": str(config_path),
                    "PROMPT_ROUTER_DB": str(env_database),
                    "PROMPT_ROUTER_DEFAULT_SHARING_LEVEL": "local_only",
                    "PROMPT_ROUTER_CONFIDENCE_THRESHOLD": "0.80",
                },
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["database"], str(env_database))
        self.assertEqual(payload["default_sharing_level"], "local_only")
        self.assertEqual(payload["confidence_threshold"], 0.80)

    def test_expected_command_error_is_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pr(
                "review",
                "label",
                "missing-event",
                "--sensitivity",
                "public",
                "--task-type",
                "summarize",
                "--route",
                "external_llm",
                db_path=Path(tmpdir) / "router.sqlite3",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout),
            {"error": "event not found: missing-event"},
        )
        self.assertEqual(result.stderr, "")

    def test_invalid_configuration_error_is_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("{", encoding="utf-8")
            result = self.run_pr(
                "status",
                extra_env={"PROMPT_ROUTER_CONFIG": str(config_path)},
            )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIn("invalid JSON", payload["error"])
        self.assertEqual(result.stderr, "")

    def test_file_output_error_is_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_directory = Path(tmpdir) / "dataset-directory"
            output_directory.mkdir()
            result = self.run_pr(
                "dataset",
                "build",
                "--output",
                str(output_directory),
                db_path=Path(tmpdir) / "router.sqlite3",
            )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["error"])
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
