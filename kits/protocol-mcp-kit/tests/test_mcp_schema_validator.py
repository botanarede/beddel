"""Tests for MCP schema validation utility.

Validates ``validate_tool_arguments`` against various schema scenarios.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from beddel_protocol_mcp.schema_validator import validate_tool_arguments
from jsonschema import ValidationError

from beddel.domain.errors import MCPError
from beddel.error_codes import MCP_SCHEMA_VALIDATION_FAILED

# Synthetic sensitive markers: none of them may ever appear in the raised error.
VALUE_MARKER = "KIT-SECRET-VALUE-MARKER"
KEY_MARKER = "KIT-SECRET-KEY-MARKER"

FIXED_MESSAGE = "Tool arguments failed schema validation"

# ---------------------------------------------------------------------------
# Shared schema fixture
# ---------------------------------------------------------------------------

SAMPLE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateToolArguments:
    """Tests for validate_tool_arguments utility."""

    def test_valid_arguments_pass(self) -> None:
        """Valid arguments against a schema with required string and integer fields."""
        # Should not raise
        validate_tool_arguments({"name": "Alice", "age": 30}, SAMPLE_SCHEMA)

    def test_missing_required_field_raises(self) -> None:
        """Missing required field raises MCPError(MCP_SCHEMA_VALIDATION_FAILED)."""
        with pytest.raises(MCPError) as exc_info:
            validate_tool_arguments({"name": "Alice"}, SAMPLE_SCHEMA)
        assert exc_info.value.code == MCP_SCHEMA_VALIDATION_FAILED
        assert exc_info.value.message == FIXED_MESSAGE
        assert exc_info.value.details == {"keyword": "required"}

    def test_wrong_type_raises(self) -> None:
        """Wrong type for a field raises MCPError(MCP_SCHEMA_VALIDATION_FAILED)."""
        with pytest.raises(MCPError) as exc_info:
            validate_tool_arguments({"name": "Alice", "age": "not-an-int"}, SAMPLE_SCHEMA)
        assert exc_info.value.code == MCP_SCHEMA_VALIDATION_FAILED
        assert exc_info.value.message == FIXED_MESSAGE
        assert exc_info.value.details == {"keyword": "type"}

    def test_empty_schema_passes(self) -> None:
        """Empty schema {} accepts any arguments."""
        # Should not raise
        validate_tool_arguments({"anything": "goes", "count": 42}, {})

    def test_import_guard(self) -> None:
        """When jsonschema is unavailable, importing raises ImportError."""
        import importlib

        import beddel_protocol_mcp.schema_validator as mod

        with (
            patch.dict("sys.modules", {"jsonschema": None}),
            pytest.raises(ImportError, match="jsonschema not installed"),
        ):
            importlib.reload(mod)

        # Restore the module so other tests are not affected
        importlib.reload(mod)


class TestValidationErrorLeaksNothing:
    """The raised error must not carry argument values, keys or jsonschema text."""

    @pytest.mark.parametrize(
        ("schema", "arguments", "keyword"),
        [
            pytest.param(
                {"type": "object", "properties": {"count": {"type": "integer"}}},
                {"count": VALUE_MARKER},
                "type",
                id="type-value",
            ),
            pytest.param(
                {"type": "object", "properties": {"count": {"type": "integer"}}},
                {KEY_MARKER: 1, "count": VALUE_MARKER},
                "type",
                id="type-with-marker-key",
            ),
            pytest.param(
                {"type": "object", "required": ["name"]},
                {KEY_MARKER: VALUE_MARKER},
                "required",
                id="required-with-marker-key-and-value",
            ),
            pytest.param(
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "additionalProperties": False,
                },
                {"name": "Alice", KEY_MARKER: VALUE_MARKER},
                "additionalProperties",
                id="additional-properties-marker-key",
            ),
            pytest.param(
                {"type": "object", "properties": {"mode": {"enum": ["fast", "slow"]}}},
                {"mode": VALUE_MARKER},
                "enum",
                id="enum-value",
            ),
            pytest.param(
                {
                    "type": "object",
                    "properties": {"slug": {"type": "string", "pattern": "^[a-z]+$"}},
                },
                {"slug": VALUE_MARKER},
                "pattern",
                id="pattern-value",
            ),
            pytest.param(
                {
                    "type": "object",
                    "properties": {
                        "outer": {
                            "type": "object",
                            "properties": {"inner": {"type": "integer"}},
                        }
                    },
                },
                {"outer": {"inner": VALUE_MARKER}},
                "type",
                id="nested-object-value",
            ),
            pytest.param(
                {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"count": {"type": "integer"}},
                                "additionalProperties": False,
                            },
                        }
                    },
                },
                {"items": [{"count": 1}, {"count": 2, KEY_MARKER: VALUE_MARKER}]},
                "additionalProperties",
                id="array-item-marker-key",
            ),
            pytest.param(
                {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"count": {"type": "integer"}},
                            },
                        }
                    },
                },
                {"items": [{"count": 1}, {"count": VALUE_MARKER}]},
                "type",
                id="array-item-value",
            ),
            pytest.param(
                {
                    "type": "object",
                    "properties": {
                        "outer": {
                            "type": "object",
                            "additionalProperties": {"type": "integer"},
                        }
                    },
                },
                {"outer": {KEY_MARKER: VALUE_MARKER}},
                "type",
                id="nested-marker-key-in-path",
            ),
        ],
    )
    def test_error_is_free_of_argument_data(
        self, schema: dict, arguments: dict, keyword: str
    ) -> None:
        with pytest.raises(MCPError) as exc_info:
            validate_tool_arguments(arguments, schema)

        err = exc_info.value
        assert err.code == MCP_SCHEMA_VALIDATION_FAILED
        assert err.message == FIXED_MESSAGE
        assert err.details == {"keyword": keyword}
        assert str(err) == f"{MCP_SCHEMA_VALIDATION_FAILED}: {FIXED_MESSAGE}"

        surfaces = {
            "str": str(err),
            "repr": repr(err),
            "message": err.message,
            "details": json.dumps(err.details),
            "args": repr(err.args),
        }
        for name, text in surfaces.items():
            assert VALUE_MARKER not in text, f"value marker leaked via {name}"
            assert KEY_MARKER not in text, f"key marker leaked via {name}"

        assert err.__cause__ is None
        assert err.__context__ is None

    def test_no_validation_error_survives_in_traceback_frames(self) -> None:
        """The traceback of the raised error holds no ValidationError reference."""
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
        with pytest.raises(MCPError) as exc_info:
            validate_tool_arguments({"count": VALUE_MARKER, KEY_MARKER: 1}, schema)

        tb = exc_info.value.__traceback__
        assert tb is not None
        while tb is not None:
            for name, value in tb.tb_frame.f_locals.items():
                assert not isinstance(value, ValidationError), f"{name} holds a ValidationError"
            tb = tb.tb_next

    def test_message_is_identical_for_every_failure(self) -> None:
        """Different failures, same message: nothing input-dependent is in it."""
        messages = set()
        for schema, arguments in (
            ({"type": "object", "required": ["a"]}, {}),
            ({"type": "object", "properties": {"a": {"type": "integer"}}}, {"a": "x"}),
            ({"type": "object", "additionalProperties": False}, {"b": 1}),
        ):
            with pytest.raises(MCPError) as exc_info:
                validate_tool_arguments(arguments, schema)
            messages.add(exc_info.value.message)
        assert messages == {FIXED_MESSAGE}

    def test_unrecognised_failure_reports_unknown_keyword(self) -> None:
        """A ValidationError without a keyword string still yields a safe error."""
        raw = ValidationError(f"{VALUE_MARKER} {KEY_MARKER}", instance=VALUE_MARKER)
        with (
            patch("beddel_protocol_mcp.schema_validator.validate", side_effect=raw),
            pytest.raises(MCPError) as exc_info,
        ):
            validate_tool_arguments({KEY_MARKER: VALUE_MARKER}, {})

        err = exc_info.value
        assert err.code == MCP_SCHEMA_VALIDATION_FAILED
        assert err.message == FIXED_MESSAGE
        assert err.details == {"keyword": "unknown"}
        assert VALUE_MARKER not in repr(err) + json.dumps(err.details)
        assert KEY_MARKER not in repr(err) + json.dumps(err.details)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_valid_nested_arguments_still_pass(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"count": {"type": "integer"}},
                        "additionalProperties": False,
                    },
                }
            },
        }
        validate_tool_arguments({"items": [{"count": 1}, {"count": 2}]}, schema)
