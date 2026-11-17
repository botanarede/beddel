"""Operator install and verification for the global Beddel Delivery agent."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

__all__ = ["install", "main", "render", "verify"]

_AGENT_NAME = "beddel-delivery"
_TEMPLATE = Path(__file__).with_name("beddel-delivery.template.json")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(pointers_dir: Path) -> bytes:
    """Render the stable agent configuration for *pointers_dir*."""
    template = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    python_dir = Path(__file__).resolve().parent.parent
    command = (
        f"env PYTHONPATH={shlex.quote(str(python_dir))} python3 -P -m "
        f"beddel_agent_kiro.hook --pointers {shlex.quote(str(pointers_dir.resolve()))}"
    )
    for entry in template["hooks"]:
        entry["action"]["command"] = command
    return _canonical_bytes(template)


def _agent_path(home: Path) -> Path:
    return home / ".kiro" / "agents" / f"{_AGENT_NAME}.json"


def _private_dir(path: Path) -> None:
    created = False
    if path.exists():
        if not path.is_dir() or path.is_symlink():
            raise OSError(f"not a directory: {path}")
    else:
        path.mkdir(parents=True, mode=0o700)
        created = True
    if created:
        os.chmod(path, 0o700)


def install(home: Path, pointers_dir: Path, replace: bool = False) -> tuple[Path, str]:
    """Install the agent config and secure pointer directory under *home*."""
    target = _agent_path(home)
    rendered = render(pointers_dir)
    expected = _digest(rendered)
    home.mkdir(parents=True, exist_ok=True)
    _private_dir(home / ".kiro")
    _private_dir(target.parent)
    _private_dir(pointers_dir)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or target.read_bytes() != rendered:
            if not replace:
                raise FileExistsError(f"{target} differs; use --replace")
        else:
            os.chmod(target, 0o600)
            return target, expected
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temporary, flags, 0o600)
    try:
        view = memoryview(rendered)
        while view:
            view = view[os.write(fd, view) :]
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, target)
    os.chmod(target, 0o600)
    return target, expected


def verify(home: Path, pointers_dir: Path) -> tuple[bool, str, str]:
    """Compare the installed agent against the rendered template."""
    expected_raw = render(pointers_dir)
    expected = _digest(expected_raw)
    target = _agent_path(home)
    if not target.is_file() or target.is_symlink():
        return False, expected, "missing"
    try:
        found = _digest(target.read_bytes())
    except OSError:
        return False, expected, "missing"
    return found == expected, expected, found


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or verify the Beddel Delivery agent"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--home", type=Path, default=Path.home())
        command.add_argument("--pointers", type=Path, default=None)
        if name == "install":
            command.add_argument("--replace", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the operator command and return its process exit code."""
    args = _parser().parse_args(argv)
    home = args.home.expanduser().resolve()
    pointers = (
        (
            args.pointers
            or home / ".local" / "state" / "beddel" / "kiro-hook" / "pointers"
        )
        .expanduser()
        .resolve()
    )
    if args.command == "install":
        try:
            target, digest = install(home, pointers, args.replace)
        except (OSError, ValueError, KeyError) as error:
            print(f"install failed: {error}", file=sys.stderr)
            return 1
        print(f"installed {target} sha256={digest}")
        print(f"pointers {pointers}")
        return 0
    try:
        ok, expected, found = verify(home, pointers)
    except (OSError, ValueError, KeyError) as error:
        print(f"verify failed: {error}", file=sys.stderr)
        return 1
    if ok:
        print(f"ok {expected}")
        return 0
    print(f"drift expected={expected} found={found}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
