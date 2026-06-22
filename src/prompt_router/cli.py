from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .classifier import classify_prompt
from .config import Config, ConfigError, load_config
from .constants import CLASSIFIER_VERSION, POLICY_VERSION
from .db import (
    connect,
    insert_event,
    label_review_case,
    list_events,
    list_review_cases,
    sync_plan,
    training_examples,
)
from .policy import decide_route
from .redactor import redact
from .schemas import SchemaValidationError, validated_route_output
from .semantic import (
    SemanticConfigError,
    SemanticResult,
    semantic_check,
)


def prompt_hash(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pr", description="Local-first prompt classification and routing CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show local prompt-router status")

    classify = sub.add_parser("classify", help="Classify prompt sensitivity and task type")
    classify.add_argument("prompt")
    classify.add_argument(
        "--with-semantic-check",
        action="store_true",
        help="Apply the opt-in local semantic risk amplifier",
    )

    route = sub.add_parser("route", help="Return routing decision for a prompt")
    route.add_argument("prompt")
    route.add_argument(
        "--with-semantic-check",
        action="store_true",
        help="Apply the opt-in local semantic risk amplifier",
    )

    semantic_parser = sub.add_parser(
        "semantic-check",
        help="Run the local deterministic semantic similarity check",
    )
    semantic_parser.add_argument("prompt")

    redact_parser = sub.add_parser("redact", help="Redact detected entities in a prompt")
    redact_parser.add_argument("prompt")
    redact_parser.add_argument(
        "--json",
        action="store_true",
        help="Compatibility flag; output is always structured JSON",
    )

    run = sub.add_parser("run", help="Classify, route, and log a prompt; no real model calls in starter repo")
    run.add_argument("prompt")
    run.add_argument("--dry-run", action="store_true", help="Do not persist event")
    run.add_argument("--store-raw", action="store_true", help="Store raw prompt locally. Not recommended for production defaults.")
    run.add_argument("--sharing-level", default=None)
    run.add_argument(
        "--with-semantic-check",
        action="store_true",
        help="Apply the opt-in local semantic risk amplifier",
    )

    events = sub.add_parser("events", help="Event commands")
    events_sub = events.add_subparsers(dest="events_command", required=True)
    events_list = events_sub.add_parser("list", help="List recent events")
    events_list.add_argument("--limit", type=int, default=20)

    review = sub.add_parser("review", help="Review commands")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_list = review_sub.add_parser("list", help="List pending review cases")
    review_list.add_argument("--reason", default=None)
    review_list.add_argument("--limit", type=int, default=20)

    review_label = review_sub.add_parser("label", help="Apply human label to an event")
    review_label.add_argument("event_id")
    review_label.add_argument("--sensitivity", required=True)
    review_label.add_argument("--task-type", required=True)
    review_label.add_argument("--route", required=True)
    review_label.add_argument("--note", default=None)
    review_label.add_argument("--approve-training", action="store_true")
    review_label.add_argument("--training-text-type", default="redacted", choices=["redacted", "features_only", "raw"])

    dataset = sub.add_parser("dataset", help="Dataset commands")
    dataset_sub = dataset.add_subparsers(dest="dataset_command", required=True)
    dataset_build = dataset_sub.add_parser("build", help="Build JSONL dataset from approved training examples")
    dataset_build.add_argument("--output", required=True)

    sync = sub.add_parser("sync", help="Sync commands")
    sync.add_argument("--dry-run", action="store_true", help="Only dry-run is supported in starter repo")
    sync.add_argument("--limit", type=int, default=50)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
        if args.command == "status":
            return cmd_status(config)
        if args.command == "classify":
            return cmd_classify(
                args.prompt,
                config,
                with_semantic_check=args.with_semantic_check,
            )
        if args.command == "route":
            return cmd_route(
                args.prompt,
                config,
                with_semantic_check=args.with_semantic_check,
            )
        if args.command == "semantic-check":
            return cmd_semantic_check(args.prompt)
        if args.command == "redact":
            return cmd_redact(args.prompt, json_output=args.json)
        if args.command == "run":
            sharing_level = (
                args.sharing_level
                if args.sharing_level is not None
                else config.default_sharing_level
            )
            return cmd_run(
                args.prompt,
                dry_run=args.dry_run,
                store_raw=args.store_raw,
                sharing_level=sharing_level,
                config=config,
                with_semantic_check=args.with_semantic_check,
            )
        if args.command == "events" and args.events_command == "list":
            return cmd_events_list(args.limit, config)
        if args.command == "review" and args.review_command == "list":
            return cmd_review_list(reason=args.reason, limit=args.limit, config=config)
        if args.command == "review" and args.review_command == "label":
            return cmd_review_label(args, config)
        if args.command == "dataset" and args.dataset_command == "build":
            return cmd_dataset_build(args.output, config)
        if args.command == "sync":
            return cmd_sync(dry_run=args.dry_run, limit=args.limit, config=config)
    except (
        ConfigError,
        SemanticConfigError,
        SchemaValidationError,
        ValueError,
        OSError,
        sqlite3.Error,
    ) as exc:
        print_json({"error": str(exc)})
        return 1

    parser.error("unknown command")
    return 2


def cmd_status(config: Config) -> int:
    print_json(
        {
            "mode": "local_first",
            "database": str(config.database),
            "config_file": str(config.config_file),
            "policy_version": POLICY_VERSION,
            "classifier_version": CLASSIFIER_VERSION,
            "confidence_threshold": config.confidence_threshold,
            "sync_enabled": False,
            "default_sharing_level": config.default_sharing_level,
        }
    )
    return 0


def cmd_classify(
    prompt: str,
    config: Config,
    *,
    with_semantic_check: bool,
) -> int:
    result = classify_prompt(prompt)
    semantic = _optional_semantic_check(prompt, with_semantic_check)
    decision = decide_route(
        result,
        confidence_threshold=config.confidence_threshold,
        semantic=semantic,
    )
    payload = result.to_dict()
    if semantic is not None:
        payload["semantic"] = semantic.to_dict()
    payload["routing"] = validated_route_output(decision)
    print_json(payload)
    return 0


def cmd_route(
    prompt: str,
    config: Config,
    *,
    with_semantic_check: bool,
) -> int:
    result = classify_prompt(prompt)
    semantic = _optional_semantic_check(prompt, with_semantic_check)
    decision = decide_route(
        result,
        confidence_threshold=config.confidence_threshold,
        semantic=semantic,
    )
    print_json(validated_route_output(decision))
    return 0


def cmd_semantic_check(prompt: str) -> int:
    print_json(semantic_check(prompt).to_dict())
    return 0


def cmd_redact(prompt: str, *, json_output: bool) -> int:
    result = redact(prompt)
    print_json(result.to_dict())
    return 0


def cmd_run(
    prompt: str,
    *,
    dry_run: bool,
    store_raw: bool,
    sharing_level: str,
    config: Config,
    with_semantic_check: bool,
) -> int:
    classification = classify_prompt(prompt)
    semantic = _optional_semantic_check(prompt, with_semantic_check)
    decision = decide_route(
        classification,
        confidence_threshold=config.confidence_threshold,
        semantic=semantic,
    )
    routing = validated_route_output(decision)
    payload: dict[str, Any] = {
        "dry_run": dry_run,
        "prompt_hash": prompt_hash(prompt),
        "classification": classification.to_dict(),
        "routing": routing,
        "execution": _placeholder_execution(decision.route),
    }
    if semantic is not None:
        payload["semantic"] = semantic.to_dict()

    if not dry_run:
        with connect(config.database) as conn:
            event_id = insert_event(
                conn,
                prompt_hash=prompt_hash(prompt),
                prompt=prompt,
                store_raw=store_raw,
                classification=classification,
                decision=decision,
                sharing_level=sharing_level,
            )
        payload["event_id"] = event_id
        payload["raw_prompt_stored"] = store_raw

    print_json(payload)
    return 0


def _optional_semantic_check(
    prompt: str,
    enabled: bool,
) -> SemanticResult | None:
    return semantic_check(prompt) if enabled else None


def _placeholder_execution(route: str) -> dict[str, Any]:
    return {
        "executed": False,
        "executor": route,
        "note": "Starter repo does not call real internal or external models.",
    }


def cmd_events_list(limit: int, config: Config) -> int:
    with connect(config.database) as conn:
        print_json(list_events(conn, limit=limit))
    return 0


def cmd_review_list(reason: str | None, limit: int, config: Config) -> int:
    with connect(config.database) as conn:
        print_json(list_review_cases(conn, reason=reason, limit=limit))
    return 0


def cmd_review_label(args: argparse.Namespace, config: Config) -> int:
    label = {
        "sensitivity": args.sensitivity,
        "task_type": args.task_type,
        "route": args.route,
    }
    with connect(config.database) as conn:
        result = label_review_case(
            conn,
            event_id=args.event_id,
            label=label,
            notes=args.note,
            approve_training=args.approve_training,
            training_text_type=args.training_text_type,
        )
    print_json(result)
    return 0


def cmd_dataset_build(output: str, config: Config) -> int:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(config.database) as conn:
        examples = training_examples(conn)
    with path.open("w", encoding="utf-8") as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")
    print_json({"output": str(path), "examples": len(examples)})
    return 0


def cmd_sync(*, dry_run: bool, limit: int, config: Config) -> int:
    if not dry_run:
        print_json({"error": "Only --dry-run is supported in starter repo."})
        return 1
    with connect(config.database) as conn:
        print_json(sync_plan(conn, limit=limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
