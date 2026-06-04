"""Configure sys.path for standalone kit test execution.

Adds the kit's ``python/`` directory to ``sys.path`` so that
``import beddel_auth_firebase`` resolves when running ``pytest`` from the kit
root. ``firebase-admin``, ``google-cloud-firestore``, ``pydantic`` and
``fastapi`` must be installed in the environment.
"""

from __future__ import annotations

import sys
from pathlib import Path

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))
