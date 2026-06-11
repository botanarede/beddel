"""Configure sys.path for standalone kit test execution.

Adds the kit's ``python/`` to sys.path so ``import beddel_agent_claude``
resolves.  Also adds the SDK test helpers path so ``_helpers.make_context``
is importable.
The ``beddel`` SDK itself must be installed (``pip install beddel``).
"""

import sys
from pathlib import Path

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))

# Add the main SDK tests/ directory for _helpers.py access
_SDK_TESTS = _KIT_ROOT.parent.parent.parent / "src" / "beddel-py" / "tests"
if _SDK_TESTS.exists():
    sys.path.insert(0, str(_SDK_TESTS))
