from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .constants import DEFAULT_CONFIDENCE_THRESHOLD, DEFAULT_SHARING_LEVEL

DEFAULT_CONFIG_PATH = Path.home() / ".prompt-router" / "config.json"
DEFAULT_DATABASE_PATH = Path.home() / ".prompt-router" / "prompt_router.sqlite3"
SUPPORTED_KEYS = {
    "database",
    "default_sharing_level",
    "confidence_threshold",
}


class ConfigError(ValueError):
    """Raised when local prompt-router configuration is invalid."""


@dataclass(frozen=True)
class Config:
    database: Path
    default_sharing_level: str
    confidence_threshold: float
    config_file: Path


def load_config(
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Config:
    env = os.environ if environ is None else environ
    selected_path = (
        Path(config_path)
        if config_path is not None
        else Path(env.get("PROMPT_ROUTER_CONFIG", DEFAULT_CONFIG_PATH))
    ).expanduser()
    file_values = _load_file(selected_path)

    database_value = env.get(
        "PROMPT_ROUTER_DB",
        file_values.get("database", str(DEFAULT_DATABASE_PATH)),
    )
    sharing_level = env.get(
        "PROMPT_ROUTER_DEFAULT_SHARING_LEVEL",
        file_values.get("default_sharing_level", DEFAULT_SHARING_LEVEL),
    )
    threshold_value: object = env.get(
        "PROMPT_ROUTER_CONFIDENCE_THRESHOLD",
        file_values.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD),
    )

    database = _database_path(database_value)
    validated_sharing_level = _sharing_level(sharing_level)
    confidence_threshold = _confidence_threshold(threshold_value)

    return Config(
        database=database,
        default_sharing_level=validated_sharing_level,
        confidence_threshold=confidence_threshold,
        config_file=selected_path,
    )


def _load_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in config file {path}: {exc.msg}") from exc

    if not isinstance(value, dict):
        raise ConfigError(f"config file {path} must contain a JSON object")
    unknown_keys = sorted(set(value) - SUPPORTED_KEYS)
    if unknown_keys:
        raise ConfigError(f"unknown config key: {unknown_keys[0]}")
    return value


def _database_path(value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("database must be a non-empty string path")
    return Path(value).expanduser()


def _sharing_level(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("default sharing level must be a non-empty string")
    return value


def _confidence_threshold(value: object) -> float:
    if isinstance(value, bool):
        raise ConfigError("confidence threshold must be a number from 0.0 to 1.0")
    try:
        threshold = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            "confidence threshold must be a number from 0.0 to 1.0"
        ) from exc
    if not 0.0 <= threshold <= 1.0:
        raise ConfigError("confidence threshold must be a number from 0.0 to 1.0")
    return threshold
