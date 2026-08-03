"""Enablement-safety tests for serve-a2a-kit (Story K1A.5, AC8).

Where ``test_a2a_integration.py`` asks *"does A2A behave correctly once
mounted?"* and ``test_a2a_smoke.py`` asks *"does it work over a real socket?"*,
this module asks the opposite question: **when must A2A not be there at all?**

The subject under test is therefore not this kit's ``server.py`` but the
mounting gate in ``beddel.cli.commands._build_runtime_app``::

    _a2a_kit_available = (not no_kits
                          and _index_available
                          and "serve-a2a-kit" in _enabled_kit_names)
                         if _index_available else False

    if   a2a_enable and     _a2a_kit_available:  -> mount (fail loud on ImportError)
    elif a2a_enable and not _a2a_kit_available:  -> logger.debug, mount nothing

Two axes, four quadrants, and the tests below pin every one of them:

===================  =================  ===========================
``a2a_enable``       kit in index       expected outcome
===================  =================  ===========================
``False`` (default)  yes                no A2A routes  (cases 1, 5)
``True``             no / disabled      no A2A routes, no raise (2)
``True``             yes, unimportable  ``click.ClickException`` (3)
``True``             yes                A2A routes  (positive control)
===================  =================  ===========================

The unimportable quadrant matters on its own: a silent skip and a loud failure
are *different code paths*, and conflating them is exactly how "A2A quietly
stopped being served" ships to production.

Hermetic environment
--------------------
``_build_runtime_app`` reads the SQLite kit index (``~/.config/beddel/index.db``),
the global config (``~/.config/beddel/config.json``), a project-local
``.beddel.json`` found by walking up from the CWD, and mutates ``sys.path``.
Running it in-process against a developer's real environment would be both
non-deterministic and destructive, so :func:`runtime_env` redirects all four:

* ``HOME`` -> a temp dir (``IndexStore`` expands ``~`` at call time, so a fresh
  empty index is created per test and the developer's own enabled/disabled kit
  selection is never read or written);
* ``beddel.cli.config.GLOBAL_CONFIG_PATH`` -> the temp config (that module
  expands ``~`` at *import* time, so patching ``HOME`` alone is not enough);
* CWD -> the temp dir, so no repository ``.beddel.json`` can win the
  project-config layer;
* ``sys.path`` -> a copy, restored on teardown.

``kits_paths`` points at a per-test *kit farm*: a directory of symlinks to just
the kits a given scenario needs. That is what makes "serve-a2a-kit is absent"
expressible without uninstalling anything, and it keeps each build to three
kits instead of the ~46 in ``repo/kits``.

Non-vacuity
-----------
Absence assertions pass just as happily when the whole app failed to build, so
every "no A2A route" test also asserts the app *did* build (``/health`` plus the
generated workflow route), and the two ``a2a_enable=False`` tests additionally
assert ``serve-a2a-kit`` really is enabled in the index — pinning the flag, not
the environment, as the reason A2A is missing.
``test_control_a2a_enable_with_kit_present_mounts_routes`` is the standing
positive control for the harness as a whole.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Environment guards
# ---------------------------------------------------------------------------

pytest.importorskip("a2a", reason="a2a-sdk not installed")
pytest.importorskip("beddel.cli.commands", reason="beddel SDK not installed")

import click  # noqa: E402 - keep the importorskip guards above first

_KITS_DIR = Path(__file__).resolve().parents[2]
"""``repo/kits`` — the source of the symlinks placed in each kit farm."""

_SERVE_KIT = "serve-a2a-kit"
_AGENT_KIT = "agent-a2a-kit"
_FASTAPI_KIT = "serve-fastapi-kit"
_AGUI_KIT = "ag-ui-kit"

_REQUIRED_KITS = (_FASTAPI_KIT, _SERVE_KIT, _AGENT_KIT, _AGUI_KIT)

_missing = [
    name for name in _REQUIRED_KITS if not (_KITS_DIR / name / "kit.yaml").is_file()
]
if _missing:
    pytest.skip(
        f"kits not found under the expected repo/kits/ layout: {_missing}; "
        "the enablement gate cannot be exercised",
        allow_module_level=True,
    )


pytestmark = pytest.mark.integration
"""Module-wide ``integration`` marker (Story K1A.5, AC7).

Declared *after* the ``importorskip`` / ``skip(allow_module_level=True)`` guards
above so a missing dependency still short-circuits collection cleanly.  These
tests build real FastAPI apps against a real SQLite kit index and real kit
discovery, so they belong in the same selective-CI bucket as the other
Story-K1A.5 modules.
"""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WORKFLOW_ID = "a2a_enablement_echo"

_WORKFLOW_YAML = f"""\
# Generated by test_a2a_enablement.py — deliberately provider-free.
id: {_WORKFLOW_ID}
name: A2A Enablement Echo
description: Renders a fixed string without calling any external provider.
version: "1.0"
steps:
  - id: echo
    primitive: output-generator
    config:
      format: text
      template: "a2a-enablement-ok"
"""

_A2A_ROUTES = frozenset(
    {
        "/a2a",
        "/.well-known/agent-card.json",
        "/.well-known/agent.json",  # legacy 301 alias, registered in the same block
    }
)
"""Every route path ``_build_runtime_app`` adds inside the A2A block."""

_WORKFLOW_ROUTE = f"/workflows/{_WORKFLOW_ID}/"
"""Proof-of-life route: present whenever the app built and mounted the flow."""

_SKIP_LOG_FRAGMENT = "A2A not mounted"
_IMPORT_FAILURE_FRAGMENT = "beddel_serve_a2a is not importable"

_COMMANDS_LOGGER = "beddel.cli.commands"


# ---------------------------------------------------------------------------
# Hermetic runtime environment
# ---------------------------------------------------------------------------


def _write_kit_farm(root: Path, kit_names: Sequence[str]) -> Path:
    """Create a kits directory holding symlinks to *kit_names* and return it."""
    farm = root / "kits"
    farm.mkdir()
    for name in kit_names:
        (farm / name).symlink_to(_KITS_DIR / name, target_is_directory=True)
    return farm


def _write_hermetic_home(root: Path, farm: Path) -> Path:
    """Create the throw-away ``HOME`` (config + one flow) and return its path."""
    home = root / "home"
    config_dir = home / ".config" / "beddel"
    config_dir.mkdir(parents=True)
    flows_dir = root / "flows"
    flows_dir.mkdir()
    (flows_dir / "a2a-enablement-echo.yaml").write_text(
        _WORKFLOW_YAML, encoding="utf-8"
    )
    (config_dir / "config.json").write_text(
        json.dumps({"kits_paths": [str(farm)], "flows_paths": [str(flows_dir)]}),
        encoding="utf-8",
    )
    return home


@pytest.fixture
def runtime_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Path]:
    """Return ``prepare(kit_names) -> farm`` for a hermetic ``_build_runtime_app``.

    Calling ``prepare`` redirects ``HOME``, the global-config path, the CWD and
    ``sys.path`` (see the module docstring) and returns the kit farm directory,
    which callers need when they want to drive ``discover_kits`` themselves.
    """
    import beddel.cli.config as beddel_config

    def _prepare(kit_names: Sequence[str]) -> Path:
        farm = _write_kit_farm(tmp_path, kit_names)
        home = _write_hermetic_home(tmp_path, farm)

        monkeypatch.setenv("HOME", str(home))
        for var in (
            "XDG_CONFIG_HOME",
            "A2A_AUTH_TOKEN",
            "A2A_PUBLIC_URL",
            "BEDDEL_KIT_PATHS",
        ):
            monkeypatch.delenv(var, raising=False)

        # config.py expands ``~`` at import time — HOME alone would not move it.
        monkeypatch.setattr(
            beddel_config,
            "GLOBAL_CONFIG_PATH",
            home / ".config" / "beddel" / "config.json",
        )
        # Keeps ``find_project_config()`` from walking into the repository.
        monkeypatch.chdir(tmp_path)
        # ``_ensure_kit_paths()`` prepends farm dirs; hand it a disposable list.
        monkeypatch.setattr(sys, "path", list(sys.path))
        return farm

    return _prepare


def _route_paths(app: Any) -> set[str]:
    """Collect ``.path`` from every route on *app*.

    ``app.routes`` mixes ``APIRoute``, plain ``Route`` and ``Mount``; only the
    first two carry ``path``, hence the defensive ``getattr``.
    """
    return {
        path
        for route in app.routes
        if (path := getattr(route, "path", None)) is not None
    }


def _enabled_kit_names() -> set[str]:
    """Read the enabled kit names straight from the hermetic index."""
    from beddel.adapters.index_store import IndexStore

    return {
        row["name"] for row in asyncio.run(IndexStore().list_kits(enabled_only=True))
    }


def _assert_app_built(routes: set[str]) -> None:
    """Guard against absence assertions passing on a half-built app."""
    assert "/health" in routes, f"app did not finish building: {sorted(routes)}"
    assert _WORKFLOW_ROUTE in routes, (
        f"generated workflow was not mounted, so this app proves nothing: {sorted(routes)}"
    )


# ---------------------------------------------------------------------------
# Case 1 — a2a_enable defaults to False
# ---------------------------------------------------------------------------


def test_default_build_mounts_no_a2a_routes(runtime_env: Callable[..., Path]) -> None:
    """The default ``a2a_enable=False`` yields no A2A routes even with the kit enabled.

    This is the shape ``connect`` and ``launch`` get. ``serve-a2a-kit`` is in the
    farm and enabled in the index, so ``_a2a_kit_available`` is True and the
    *only* thing withholding A2A is the flag — which is precisely the guarantee
    AC8 asks for.
    """
    runtime_env([_FASTAPI_KIT, _SERVE_KIT])
    from beddel.cli.commands import _build_runtime_app

    app, _loaded, wf_ids = _build_runtime_app(())
    routes = _route_paths(app)

    _assert_app_built(routes)
    assert wf_ids == [_WORKFLOW_ID]
    assert _SERVE_KIT in _enabled_kit_names(), (
        "kit was not enabled in the index — absence of A2A would be attributable "
        "to the gate's kit check rather than to a2a_enable=False"
    )
    assert routes & _A2A_ROUTES == set(), (
        f"A2A routes leaked into a default build: {routes}"
    )


# ---------------------------------------------------------------------------
# Positive control — the harness can observe a mounted A2A
# ---------------------------------------------------------------------------


def test_control_a2a_enable_with_kit_present_mounts_routes(
    runtime_env: Callable[..., Path],
) -> None:
    """``a2a_enable=True`` with the kit enabled mounts the A2A routes.

    Without this, every other test in this module could be passing because the
    harness is incapable of ever producing an A2A route.
    """
    runtime_env([_FASTAPI_KIT, _SERVE_KIT])
    from beddel.cli.commands import _build_runtime_app

    app, _loaded, _wf_ids = _build_runtime_app((), a2a_enable=True, port=9999)
    routes = _route_paths(app)

    _assert_app_built(routes)
    assert _A2A_ROUTES <= routes, (
        f"expected all of {sorted(_A2A_ROUTES)} in {sorted(routes)}"
    )


# ---------------------------------------------------------------------------
# Case 2 — kit absent or disabled: silent skip, no exception
# ---------------------------------------------------------------------------


def test_absent_serve_a2a_kit_skips_mounting_without_raising(
    runtime_env: Callable[..., Path], caplog: pytest.LogCaptureFixture
) -> None:
    """A farm without ``serve-a2a-kit`` skips A2A quietly, even with the flag on.

    Note the package itself stays importable (this kit's ``conftest.py`` puts it
    on ``sys.path``), so what is being pinned here is the *index* gate rather
    than an import accident.
    """
    runtime_env([_FASTAPI_KIT])
    from beddel.cli.commands import _build_runtime_app

    with caplog.at_level(logging.DEBUG, logger=_COMMANDS_LOGGER):
        app, _loaded, _wf_ids = _build_runtime_app((), a2a_enable=True, port=9999)
    routes = _route_paths(app)

    _assert_app_built(routes)
    assert _SERVE_KIT not in _enabled_kit_names()
    assert routes & _A2A_ROUTES == set(), (
        f"A2A mounted without the kit: {sorted(routes)}"
    )
    assert any(_SKIP_LOG_FRAGMENT in record.message for record in caplog.records), (
        f"expected a debug skip log; got {[r.message for r in caplog.records]}"
    )


def test_disabled_serve_a2a_kit_skips_mounting_without_raising(
    runtime_env: Callable[..., Path], caplog: pytest.LogCaptureFixture
) -> None:
    """A *present but disabled* kit is skipped too — the other half of AC8.

    Distinct from the absent case: the manifest is discovered and stays in the
    index, only ``enabled`` is 0. ``IndexStore.sync_kits`` preserves that flag
    on re-sync, which is what lets the pre-seeded 0 survive into the build.
    """
    farm = runtime_env([_FASTAPI_KIT, _SERVE_KIT])

    from beddel.adapters.index_store import IndexStore
    from beddel.cli.commands import _build_runtime_app
    from beddel.tools.kits import discover_kits

    store = IndexStore()
    asyncio.run(store.sync_kits(discover_kits([farm]).manifests))
    assert asyncio.run(store.set_kit_enabled(_SERVE_KIT, False)) is True

    with caplog.at_level(logging.DEBUG, logger=_COMMANDS_LOGGER):
        app, _loaded, _wf_ids = _build_runtime_app((), a2a_enable=True, port=9999)
    routes = _route_paths(app)

    _assert_app_built(routes)
    assert _SERVE_KIT not in _enabled_kit_names()
    assert routes & _A2A_ROUTES == set(), (
        f"A2A mounted for a disabled kit: {sorted(routes)}"
    )
    assert any(_SKIP_LOG_FRAGMENT in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Case 3 — kit enabled but the package will not import: fail loud
# ---------------------------------------------------------------------------


def test_enabled_kit_with_unimportable_package_raises_click_exception(
    runtime_env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An enabled kit whose Python package cannot be imported aborts startup.

    Setting ``sys.modules["beddel_serve_a2a"] = None`` makes ``from
    beddel_serve_a2a import ...`` raise ``ImportError`` at exactly the statement
    ``_build_runtime_app`` guards, without touching the filesystem or the kit
    farm — so the index still reports the kit as enabled and the gate really
    does enter the mounting branch.

    Contrast with the two tests above: same ``a2a_enable=True``, opposite
    contract. Silence there, ``ClickException`` here.
    """
    runtime_env([_FASTAPI_KIT, _SERVE_KIT])
    from beddel.cli.commands import _build_runtime_app

    monkeypatch.setitem(sys.modules, "beddel_serve_a2a", None)

    with pytest.raises(click.ClickException) as excinfo:
        _build_runtime_app((), a2a_enable=True, port=9999)

    assert _IMPORT_FAILURE_FRAGMENT in str(excinfo.value)
    # The remediation hint is part of the contract — a bare failure is not enough.
    assert "pip install -e" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Case 4 — client and server A2A kits installed side by side
# ---------------------------------------------------------------------------


def test_agent_and_serve_a2a_kits_load_together(
    runtime_env: Callable[..., Path],
) -> None:
    """Both A2A kits survive one ``discover_kits`` / ``load_kit_adapters`` pass.

    Locks the K1A.0B split. The pre-split unified manifest declared both an
    ``IAgentAdapter`` and the server-side ``AgentExecutor``, so
    ``load_kit_adapters`` reached ``cls()`` for ``BeddelA2AExecutor``, which
    requires a registry argument — the ``TypeError`` was swallowed by
    ``_build_adapter_registries``'s broad ``except`` and the *entire* kit was
    dropped, silently taking the client adapter with it.

    That failure mode is invisible from the outside, which is why the assertions
    are positive: the ``a2a`` agent adapter must be *present* in the registry,
    and ``serve-a2a-kit`` must contribute *no* adapters (it is a serve-tier
    integration, not a generic adapter — the point of the split).
    """
    farm = runtime_env([_FASTAPI_KIT, _AGENT_KIT, _SERVE_KIT])

    from beddel.cli.commands import _build_adapter_registries, _ensure_kit_paths
    from beddel.tools.kits import discover_kits, load_kit_adapters

    _ensure_kit_paths()  # what _build_runtime_app does: farm python/ dirs onto sys.path
    result = discover_kits([farm])

    discovered = {manifest.kit.name for manifest in result.manifests}
    assert {_AGENT_KIT, _SERVE_KIT} <= discovered, (
        f"both kits must be discovered: {discovered}"
    )

    by_kit = {manifest.kit.name: manifest for manifest in result.manifests}
    assert set(load_kit_adapters(by_kit[_AGENT_KIT])) == {("IAgentAdapter", "a2a")}
    assert load_kit_adapters(by_kit[_SERVE_KIT]) == {}, (
        "serve-a2a-kit must declare no generic adapters — a server-side "
        "AgentExecutor here is what broke the unified manifest"
    )

    agent_registry, _llm_provider, _strategies = _build_adapter_registries(result)
    assert "a2a" in agent_registry, (
        "agent-a2a-kit adapter missing — a constructor crash in this pass is "
        f"swallowed and shows up exactly like this: {sorted(agent_registry)}"
    )
    assert type(agent_registry["a2a"]).__name__ == "A2AAgentAdapter"


# ---------------------------------------------------------------------------
# Case 5 — connect / launch never acquire A2A
# ---------------------------------------------------------------------------


def test_connect_shaped_build_mounts_no_a2a_routes(
    runtime_env: Callable[..., Path],
) -> None:
    """Built the way ``connect``/``launch`` build it, the app carries no A2A.

    ``_start_runtime``, ``connect``, ``connect_dev`` and ``connect_remote`` all
    call ``_build_runtime_app(workflow_paths, dashboard=True)``; ``launch``
    passes positionally with no keywords. ``dashboard=True`` is the strictly
    larger app (AG-UI routers on top of everything ``launch`` mounts), so it is
    the shape asserted here.
    """
    runtime_env([_FASTAPI_KIT, _AGUI_KIT, _SERVE_KIT])
    from beddel.cli.commands import _build_runtime_app

    app, _loaded, _wf_ids = _build_runtime_app((), dashboard=True)
    routes = _route_paths(app)

    assert "/health" in routes, f"app did not finish building: {sorted(routes)}"
    assert f"/ag-ui/{_WORKFLOW_ID}/" in routes, (
        f"dashboard routers absent, so this is not the connect shape: {sorted(routes)}"
    )
    assert _SERVE_KIT in _enabled_kit_names(), (
        "kit was not enabled — absence of A2A must be caused by the missing "
        "a2a_enable argument, not by the index"
    )
    assert routes & _A2A_ROUTES == set(), (
        f"connect-shaped build acquired A2A: {sorted(routes)}"
    )


def test_only_serve_passes_a2a_enable_to_build_runtime_app() -> None:
    """Statically: ``serve`` is the sole call site that passes ``a2a_enable``.

    The behavioural test above covers the argument shape ``connect`` uses
    *today*; this one fails the moment a new call site starts opting in, which a
    route assertion on one hand-written shape cannot see. Parsed from source
    rather than matched textually so comments and strings cannot fake it.
    """
    import beddel.cli.commands as commands

    tree = ast.parse(Path(commands.__file__).read_text(encoding="utf-8"))

    scopes: list[tuple[int, int, str]] = [
        (node.lineno, node.end_lineno or node.lineno, node.name)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    def _enclosing(lineno: int) -> str:
        # Innermost wins, so a call nested in a closure is not misattributed.
        candidates = [
            (end - start, name) for start, end, name in scopes if start <= lineno <= end
        ]
        return min(candidates)[1] if candidates else "<module>"

    call_sites: list[tuple[str, int, bool]] = [
        (
            _enclosing(node.lineno),
            node.lineno,
            any(keyword.arg == "a2a_enable" for keyword in node.keywords),
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_build_runtime_app"
    ]

    assert call_sites, "found no _build_runtime_app call sites — the scan is broken"
    opted_in = sorted({name for name, _line, enables in call_sites if enables})
    assert opted_in == ["serve"], (
        f"only `serve` may request A2A; call sites opting in: {opted_in} "
        f"(all sites: {sorted(call_sites, key=lambda s: s[1])})"
    )
    # a2a_enable is keyword-only, so a positional call cannot smuggle it in.
    import inspect

    signature = inspect.signature(commands._build_runtime_app)
    assert signature.parameters["a2a_enable"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["a2a_enable"].default is False
