"""Shared fixtures for deploy-agent-engine-kit tests.

Adds the kit's python/ directory to sys.path so that
``import beddel_deploy_agent_engine`` resolves without installation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — add kit python/ so ``import beddel_deploy_agent_engine`` resolves.
# ---------------------------------------------------------------------------

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))
