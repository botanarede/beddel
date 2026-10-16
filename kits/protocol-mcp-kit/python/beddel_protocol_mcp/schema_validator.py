"""Schema validation utility for MCP tool arguments.

Validates tool arguments against a tool's ``inputSchema`` using the
``jsonschema`` library.  The ``jsonschema`` package is an optional
dependency (``pip install jsonschema``).  Imports are guarded with
``try/except ImportError`` to provide a clear error message when the
extra is not installed.
"""

from __future__ import annotations

from typing import Any

from beddel.domain.errors import MCPError
from beddel.error_codes import MCP_SCHEMA_VALIDATION_FAILED

try:
    from jsonschema import ValidationError, validate
except ImportError as _imp_err:
    raise ImportError(
        "jsonschema not installed. Install with: pip install jsonschema"
    ) from _imp_err

__all__ = ["validate_tool_arguments"]

# Identical for every input: jsonschema's own message embeds argument values.
_VALIDATION_FAILED_MESSAGE = "Tool arguments failed schema validation"

# Reported when jsonschema does not expose a keyword string for the failure.
_UNKNOWN_KEYWORD = "unknown"


def validate_tool_arguments(
    arguments: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """Validate tool arguments against a JSON Schema.

    The raised error is deliberately free of argument data: its message is
    fixed and ``details`` carries only the failing JSON Schema keyword
    (for example ``"type"`` or ``"required"``), which comes from the schema,
    not from the arguments.  Argument values, argument keys, the jsonschema
    message and the failing path are never reported, and the original
    ``ValidationError`` is not chained to the raised error.

    Args:
        arguments: The tool arguments to validate.
        schema: The JSON Schema to validate against (typically the
            tool's ``inputSchema``).

    Raises:
        MCPError: ``BEDDEL-MCP-603`` when arguments fail validation.
    """
    try:
        validate(instance=arguments, schema=schema)
    except ValidationError as exc:
        # Keep only the schema keyword and leave the block before raising, so
        # the ValidationError (and the data it holds) is neither the cause nor
        # the context of the error below.
        keyword = exc.validator if isinstance(exc.validator, str) else _UNKNOWN_KEYWORD
    else:
        return

    raise MCPError(
        code=MCP_SCHEMA_VALIDATION_FAILED,
        message=_VALIDATION_FAILED_MESSAGE,
        details={"keyword": keyword},
    )
