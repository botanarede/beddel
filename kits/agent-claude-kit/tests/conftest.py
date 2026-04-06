"""Configure sys.path for standalone kit test execution."""

import sys
from pathlib import Path

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "src"))

_PROJECT_ROOT = _KIT_ROOT.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src" / "beddel-py" / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "src" / "beddel-py" / "tests"))
