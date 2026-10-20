# profile-dev-kit

Development profile kit for Beddel. It provides the entry workflow
`verify-change` and a fail-closed preflight (`profile_preflight`) that checks
the target path is a Git work tree, the gate executables resolve on `PATH`, and
the required environment keys are present (key names only, never values).

Status: Story 2.2. Entry workflows `verify-change` and `ratify-inventory`; tools
`profile_preflight`, `profile_ratify_inventory` and `profile_bind_inventory`.

## Layout

```
kit.yaml                         manifest (documentation-only config block)
python/beddel_profile_dev/       Python module (tools, config)
workflows/                       entry workflows
tests/                           kit tests (no network, no real credential)
```

## Configuration

The runtime source of `GATE_EXECUTABLES`, `REQUIRED_ENV_KEYS`, `INVENTORY_DIR`
and `RECORDS_DIR` is `python/beddel_profile_dev/config.py`, resolved relative
to the kit root. The `config:` block in `kit.yaml` only documents the same
values; the core does not read it. Missing or malformed config raises; it
never degrades to empty lists.

## Inventory and ratification (Story 2.2)

An inventory version lives in the verified repository at
`.beddel-profile/inventory/<version>.yaml`: a mapping with exactly `version`
(equal to the file stem), `classes` (`{id, kind: gate|review}`), `components`
(`{id, kind: component|shared_contract, path}`), `criteria`
(`{id, description}`) and `obligations` (`{class, affected_point, criterion}`).
Ids match `^[a-z0-9][a-z0-9._-]{0,63}$`; quote ids that YAML would read as
numbers. Unknown keys are rejected.

- `ratify-inventory` (inputs `repo_path`, `inventory_version`, `actor`) writes
  `<version>.ratification.yaml` next to the version file, create-only. The
  maintainer commits it: that commit is the human act; the tool is transport.
  A ratified version is immutable; a change is a new version.
- `verify-change` (inputs `repo_path`, `revision`, `inventory_version`) runs
  `preflight`, then `bind_inventory`: it reads the version and its
  ratification from the tree of `revision`, validates identity formation and
  resolution, and either records one integrity block
  (`PROFILE_INVENTORY_INTEGRITY_BLOCK`) or writes `binding.json` and the
  canonical `snapshot.json` under `.beddel-profile/records/revisions/<sha>/`
  (local files, never committed by the kit). An unratified version stops with
  `PROFILE_INVENTORY_UNRATIFIED`; another version for an already bound
  revision stops with `PROFILE_INVENTORY_BINDING_CONFLICT`.
- A component path missing at the revision does not block binding; the
  obligation stays in the snapshot with `target_present: false`.
- Ratification hashes the work-tree bytes and binding hashes the committed
  blob: keep the version file byte-identical when committed (no EOL or
  clean-filter rewriting), otherwise binding fails closed as unratified.

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
