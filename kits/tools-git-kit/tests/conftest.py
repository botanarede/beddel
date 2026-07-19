"""Configure sys.path for standalone kit test execution.

Adds the kit's ``python/`` to sys.path so ``import beddel_tools_git``
resolves. The ``beddel`` SDK itself must be installed (``pip install beddel``).
"""

import sys
from pathlib import Path

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))
