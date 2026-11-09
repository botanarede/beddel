"""Configure standalone kit test imports and provide a deterministic fake gh."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Put a scripted fake gh executable first on PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "gh-log.jsonl"
    script_path = tmp_path / "gh-script.json"
    gh_path = bin_dir / "gh"
    gh_path.write_text(
        f"""#!{sys.executable}
import json
import os
import pathlib
import subprocess
import sys
import time

script_path = pathlib.Path(os.environ["FAKE_GH_SCRIPT"])
log_path = pathlib.Path(os.environ["FAKE_GH_LOG"])
with log_path.open("a") as stream:
    stream.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "pid": os.getpid()}}) + "\\n")
responses = json.loads(script_path.read_text())
response = responses.pop(0)
script_path.write_text(json.dumps(responses))
if response.get("mode") == "grandchild":
    child_code = "import os,time; open(os.environ['FAKE_GH_CHILD_LOG'], 'w').write(str(os.getpid())); time.sleep(60)"
    child = subprocess.Popen([sys.executable, "-c", child_code])
    pathlib.Path(os.environ["FAKE_GH_CHILD_LOG"]).write_text(str(child.pid))
if response.get("mode") in ("sleep", "grandchild"):
    time.sleep(response.get("seconds", 60))
sys.stdout.write(response.get("stdout", ""))
sys.stderr.write(response.get("stderr", ""))
sys.exit(response.get("exit", 0))
"""
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_GH_LOG", str(log_path))
    monkeypatch.setenv("FAKE_GH_SCRIPT", str(script_path))
    return tmp_path, log_path, script_path
