from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from prompt_router.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_defaults_are_used_when_config_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "missing.json"
            config = load_config(config_path=config_path, environ={})

        self.assertEqual(
            config.database,
            Path.home() / ".prompt-router" / "prompt_router.sqlite3",
        )
        self.assertEqual(config.default_sharing_level, "local_only")
        self.assertEqual(config.confidence_threshold, 0.90)
        self.assertEqual(config.config_file, config_path)

    def test_loads_supported_values_from_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            database = Path(tmpdir) / "configured.sqlite3"
            config_path.write_text(
                json.dumps(
                    {
                        "database": str(database),
                        "default_sharing_level": "redacted",
                        "confidence_threshold": 0.75,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(config_path=config_path, environ={})

        self.assertEqual(config.database, database)
        self.assertEqual(config.default_sharing_level, "redacted")
        self.assertEqual(config.confidence_threshold, 0.75)

    def test_environment_overrides_file_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            file_database = Path(tmpdir) / "file.sqlite3"
            env_database = Path(tmpdir) / "env.sqlite3"
            config_path.write_text(
                json.dumps(
                    {
                        "database": str(file_database),
                        "default_sharing_level": "redacted",
                        "confidence_threshold": 0.75,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(
                config_path=config_path,
                environ={
                    "PROMPT_ROUTER_DB": str(env_database),
                    "PROMPT_ROUTER_DEFAULT_SHARING_LEVEL": "features_only",
                    "PROMPT_ROUTER_CONFIDENCE_THRESHOLD": "0.98",
                },
            )

        self.assertEqual(config.database, env_database)
        self.assertEqual(config.default_sharing_level, "features_only")
        self.assertEqual(config.confidence_threshold, 0.98)

    def test_environment_selects_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "selected.json"
            database = Path(tmpdir) / "selected.sqlite3"
            config_path.write_text(
                json.dumps({"database": str(database)}),
                encoding="utf-8",
            )

            config = load_config(
                environ={"PROMPT_ROUTER_CONFIG": str(config_path)}
            )

        self.assertEqual(config.config_file, config_path)
        self.assertEqual(config.database, database)

    def test_rejects_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "invalid JSON"):
                load_config(config_path=config_path, environ={})

    def test_rejects_unknown_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"external_provider": "forbidden"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "unknown config key"):
                load_config(config_path=config_path, environ={})

    def test_rejects_invalid_values(self) -> None:
        invalid_values = [
            {"database": 123},
            {"default_sharing_level": ""},
            {"confidence_threshold": True},
            {"confidence_threshold": 1.1},
        ]
        for value in invalid_values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "config.json"
                config_path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ConfigError):
                    load_config(config_path=config_path, environ={})

    def test_rejects_invalid_environment_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "missing.json"
            with self.assertRaisesRegex(ConfigError, "confidence threshold"):
                load_config(
                    config_path=config_path,
                    environ={"PROMPT_ROUTER_CONFIDENCE_THRESHOLD": "high"},
                )


if __name__ == "__main__":
    unittest.main()
