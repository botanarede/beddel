"""validate_tenant tool — Node.js subprocess schema validation.

Validates tenant config JSON against @botanarede/schema TenantConfigSchema
by delegating to a Node.js subprocess (validate-schema.mjs).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from beddel_bonar_cms._errors import (
    CMS_NODE_NOT_FOUND,
    CMS_SUBPROCESS_TIMEOUT,
    CMS_VALIDATION_ERROR,
    CMSError,
)
from beddel_bonar_cms.tenant_context import get_kit_root
from beddel.utils.subprocess import SafeSubprocessRunner

__all__ = ["validate_tenant"]

_NODE_DIR = get_kit_root() / "node"
_SCRIPT_REL = Path("scripts") / "validate-schema.mjs"


def validate_tenant(tenant: dict[str, Any] | str) -> dict[str, Any]:
    """Validate a tenant config against @botanarede/schema.

    Args:
        tenant: Either a dict (tenant config) or a string (path to JSON file).
            If a dict, it is serialized to a temp file for the subprocess.

    Returns:
        Dict with keys: ``valid`` (bool), ``errors`` (list[str]), ``warnings`` (list[str]).

    Raises:
        CMSError: On validation script failure, timeout, or missing Node.js.
    """
    temp_path: Path | None = None

    try:
        # Resolve input to a file path
        if isinstance(tenant, dict):
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            json.dump(tenant, tmp)
            tmp.close()
            temp_path = Path(tmp.name)
            file_path = str(temp_path)
        else:
            file_path = tenant
            if not Path(file_path).exists():
                raise CMSError(
                    code=CMS_VALIDATION_ERROR,
                    message=f"Tenant file not found: {file_path!r}",
                    details={"path": file_path},
                )

        # Invoke Node.js validation script
        command = ["node", str(_SCRIPT_REL), file_path]

        try:
            result = SafeSubprocessRunner.run(command, cwd=str(_NODE_DIR), timeout=30)
        except FileNotFoundError as exc:
            raise CMSError(
                code=CMS_NODE_NOT_FOUND,
                message="Node.js is not available on PATH",
                details={"error": str(exc)},
            ) from exc

        # Handle timeout
        if result.timed_out:
            raise CMSError(
                code=CMS_SUBPROCESS_TIMEOUT,
                message="Schema validation script timed out after 30s",
                details={"command": command},
            )

        # Handle non-zero exit
        if result.exit_code != 0:
            raise CMSError(
                code=CMS_VALIDATION_ERROR,
                message=f"Schema validation script failed: {result.stderr}",
                details={
                    "exit_code": result.exit_code,
                    "stderr": result.stderr,
                },
            )

        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            raise CMSError(
                code=CMS_VALIDATION_ERROR,
                message=f"Malformed validation output: {result.stdout[:200]}",
                details={"stdout": result.stdout, "error": str(exc)},
            ) from exc

    finally:
        # Cleanup temp file
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
