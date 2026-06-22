from __future__ import annotations

import unittest

from prompt_router.schemas import (
    RouteDecision,
    SchemaValidationError,
    validate_route_output,
    validated_route_output,
)


class RouteSchemaTests(unittest.TestCase):
    def valid_payload(self) -> dict[str, object]:
        return {
            "route": "internal_llm",
            "allowed_external": False,
            "should_review": True,
            "review_reason": "sensitive_context",
            "executor": "internal_llm",
            "reason_codes": ["SENSITIVE_CONTEXT_INTERNAL_ONLY"],
        }

    def test_accepts_valid_route_decision(self) -> None:
        decision = RouteDecision(
            route="external_llm",
            allowed_external=True,
            should_review=False,
            review_reason=None,
            executor="external_llm",
            reason_codes=["PUBLIC_EXTERNAL_ALLOWED"],
        )

        payload = validated_route_output(decision)

        self.assertEqual(payload["route"], "external_llm")

    def test_rejects_missing_or_extra_fields(self) -> None:
        missing = self.valid_payload()
        del missing["route"]
        extra = self.valid_payload()
        extra["rationale"] = "free-form text"

        for payload in (missing, extra):
            with self.subTest(payload=payload), self.assertRaises(
                SchemaValidationError
            ):
                validate_route_output(payload)

    def test_rejects_wrong_field_types(self) -> None:
        invalid_values = {
            "route": 1,
            "allowed_external": 0,
            "should_review": "yes",
            "review_reason": 1,
            "executor": None,
            "reason_codes": "LOW_CONFIDENCE",
        }
        for field, value in invalid_values.items():
            with self.subTest(field=field):
                payload = self.valid_payload()
                payload[field] = value
                with self.assertRaises(SchemaValidationError):
                    validate_route_output(payload)

    def test_rejects_unknown_route(self) -> None:
        payload = self.valid_payload()
        payload["route"] = "internet"

        with self.assertRaisesRegex(SchemaValidationError, "unsupported route"):
            validate_route_output(payload)

    def test_rejects_external_flag_inconsistency(self) -> None:
        payload = self.valid_payload()
        payload["allowed_external"] = True

        with self.assertRaisesRegex(SchemaValidationError, "allowed_external"):
            validate_route_output(payload)

    def test_rejects_review_field_inconsistency(self) -> None:
        missing_reason = self.valid_payload()
        missing_reason["review_reason"] = None
        unexpected_reason = self.valid_payload()
        unexpected_reason["should_review"] = False

        for payload in (missing_reason, unexpected_reason):
            with self.subTest(payload=payload), self.assertRaisesRegex(
                SchemaValidationError, "review_reason"
            ):
                validate_route_output(payload)

    def test_rejects_executor_inconsistency(self) -> None:
        payload = self.valid_payload()
        payload["executor"] = "external_llm"

        with self.assertRaisesRegex(SchemaValidationError, "executor"):
            validate_route_output(payload)

    def test_rejects_malformed_reason_codes(self) -> None:
        invalid_reason_lists = [
            [""],
            ["VALID", 1],
            [" lower-case "],
        ]
        for reason_codes in invalid_reason_lists:
            with self.subTest(reason_codes=reason_codes):
                payload = self.valid_payload()
                payload["reason_codes"] = reason_codes
                with self.assertRaisesRegex(SchemaValidationError, "reason_codes"):
                    validate_route_output(payload)


if __name__ == "__main__":
    unittest.main()
