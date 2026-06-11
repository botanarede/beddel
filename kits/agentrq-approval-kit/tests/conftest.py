"""Configure sys.path for standalone kit test execution.

Adds the kit's ``python/`` to sys.path so ``import beddel_agentrq_approval``
resolves.  The ``beddel`` SDK itself must be installed (``pip install beddel``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))
