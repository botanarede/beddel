"""Tests for operator-only Delivery agent installation."""

from __future__ import annotations

import json
from pathlib import Path

from beddel_agent_kiro.agent_config import install, main, render, verify


def test_install_verify_and_refuse_drift(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    pointers = tmp_path / "pointers"
    target, digest = install(home, pointers)
    assert target == home / ".kiro/agents/beddel-delivery.json"
    assert target.stat().st_mode & 0o777 == 0o600
    assert pointers.stat().st_mode & 0o777 == 0o700
    assert verify(home, pointers) == (True, digest, digest)

    target.write_text("{}", encoding="utf-8")
    assert verify(home, pointers)[0] is False
    assert install(home, pointers, replace=True)[1] == digest
    assert main(["verify", "--home", str(home), "--pointers", str(pointers)]) == 0
    assert "ok " in capsys.readouterr().out


def test_install_refuses_different_existing_config(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    pointers = tmp_path / "pointers"
    install(home, pointers)
    target = home / ".kiro/agents/beddel-delivery.json"
    target.write_text("drift", encoding="utf-8")
    assert main(["install", "--home", str(home), "--pointers", str(pointers)]) == 1
    stderr = capsys.readouterr().err
    assert "--replace" in stderr


def test_template_invariants(tmp_path: Path) -> None:
    config = json.loads(render(tmp_path / "pointers"))
    assert config["name"] == "beddel-delivery"
    assert config["tools"] == ["glob", "grep", "read", "shell", "write"]
    assert config["allowedTools"] == []
    assert config["resources"] == []
    assert config["mcpServers"] == {}
    assert config["includeMcpJson"] is False
    assert "*" not in json.dumps(config["tools"])
    assert "@mcp" not in json.dumps(config)
    assert [entry["trigger"] for entry in config["hooks"]] == [
        "preToolUse",
        "postToolUse",
        "stop",
    ]
    for entry in config["hooks"]:
        command = entry["action"]["command"]
        assert "-m beddel_agent_kiro.hook --pointers" in command
        assert "PYTHONPATH=" in command


def test_missing_and_drift_verify_output(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    pointers = tmp_path / "pointers"
    assert main(["verify", "--home", str(home), "--pointers", str(pointers)]) == 1
    output = capsys.readouterr().out
    assert "found=missing" in output


def test_install_preserves_preexisting_kiro_mode(tmp_path: Path) -> None:
    home = tmp_path / "home"
    kiro = home / ".kiro"
    kiro.mkdir(parents=True)
    kiro.chmod(0o755)
    install(home, tmp_path / "pointers")
    assert kiro.stat().st_mode & 0o777 == 0o755
