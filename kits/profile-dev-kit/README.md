# profile-dev-kit

Development profile kit for Beddel. It provides the entry workflow
`verify-change` and a fail-closed preflight (`profile_preflight`) that checks
the target path is a Git work tree, the gate executables resolve on `PATH`, and
the required environment keys are present (key names only, never values).

Status: Story 2.1 base. Entry workflow `verify-change` and tool `profile_preflight`.

## Layout

```
kit.yaml                         manifest (documentation-only config block)
python/beddel_profile_dev/       Python module (tools, config)
workflows/                       entry workflows
tests/                           kit tests (no network, no real credential)
```

## Configuration

The runtime source of `GATE_EXECUTABLES` and `REQUIRED_ENV_KEYS` is
`python/beddel_profile_dev/config.py`, resolved relative to the kit root. The
`config:` block in `kit.yaml` only documents the same lists; the core does not
read it. Missing or malformed config raises; it never degrades to empty lists.

## Tests

```
pip install beddel pytest pytest-asyncio pyyaml
cd kits/profile-dev-kit && python -m pytest
```

The CLI tests run `beddel run` with a throw-away `HOME` whose
`.config/beddel/config.json` sets `kits_paths` to this checkout's `kits/`. To
run the workflow by hand, configure `kits_paths` the same way; passing `--kit`
alone does not put the kit's `python/` directory on `sys.path`.

## Targets

Python only (AD-15). `targets.typescript` is `unavailable`.
