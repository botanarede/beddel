# profile-dev-kit

Development profile kit for Beddel. It provides the entry workflow
`verify-change` and a fail-closed preflight (`profile_preflight`) that checks
the target path is a Git work tree, the gate executables resolve on `PATH`, and
the required environment keys are present (key names only, never values).

Status: Story 3.2. Entry workflows `verify-change`, `ratify-inventory` and
`declare-non-applicability`; tools `profile_preflight`,
`profile_ratify_inventory`, `profile_bind_inventory`, `profile_record_change`,
`profile_derive_impact`, `profile_run_gate`, `profile_run_review` and
`profile_declare_non_applicability`.

## Layout

```
kit.yaml                         manifest (documentation-only config block)
python/beddel_profile_dev/       Python module (tools, config)
workflows/                       entry workflows
tests/                           kit tests (no network, no real credential)
```

## Configuration

The runtime source of `GATE_EXECUTABLES`, `REQUIRED_ENV_KEYS`, `INVENTORY_DIR`,
`RECORDS_DIR`, `GATE_COMMANDS`, `GATE_TIMEOUT_SECONDS`,
`GATE_TOTAL_TIMEOUT_SECONDS`, `REVIEW_AGENT`, `REVIEW_MODEL` and
`REVIEW_TIMEOUT_SECONDS` is `python/beddel_profile_dev/config.py`, resolved relative
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
- `verify-change` (inputs `repo_path`, `change_id`, `base`, `revision`,
  `inventory_version`) runs
  `preflight`, `change`, `bind_inventory`, `impact`, `gate` and `review`. `bind_inventory` reads the version and its
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

## Change and Impact (Story 2.3)

- `change` (`profile_record_change`) records the Change: `change_id` (id
  pattern), its `base` commit (fixed by the first record; a rebased Change gets
  a new id, else `PROFILE_CHANGE_CONFLICT`) and the link of the Analyzed
  revision, which `base` must be an ancestor of (`PROFILE_CHANGE_INVALID`).
  Records: `.beddel-profile/records/changes/<change_id>/change.json` and
  `.../revisions/<sha>/revision.json`.
- `impact` (`profile_derive_impact`) needs the Change, its revision link and the
  binding. The footprint is the set of paths that differ between the trees of
  `base` and `revision` (plumbing, no renames, never declared by the Change).
  Affected points are the snapshot components touched by it (equal or ancestor
  by whole path segments). Required evidence is the complete derived set: every
  obligation of an Active product component present at the revision, plus every
  obligation of an Affected point, each with its Requirement ID constituents,
  `target_present` and `basis`. The result is `impact.json`, create-only and
  deterministic (`PROFILE_IMPACT_UNBOUND`, `PROFILE_IMPACT_CONFLICT`). A new
  Analyzed revision of the Change also discharges the earlier integrity blocks
  of that Change (once per block); the blocked revision stays blocked.
- `declare-non-applicability` records the maintainer's determination that one
  obligation whose component path is absent at a revision is not applicable
  there: only the actor who ratified the bound version may make it, once per
  obligation and revision (`PROFILE_DETERMINATION_REFUSED` with a reason code).
  It is a record only: it changes neither the impact record, the Required
  evidence, the snapshot, the binding nor any block.
- Ratification is also refused (`record.exists`) when its record is in the Git
  index or in the history reachable from `HEAD`; an unreadable history refuses
  with `history.unreadable`.

## Gate (Story 3.1)

`gate` (`profile_run_gate`) is the fifth step of `verify-change`. It runs the
local gate commands over the derived set that `impact.json` already holds and
records an **operational outcome**: each command's name, argv, exit code and
whether it timed out. It makes no judgement. A non-zero exit is a recorded exit
code, not a failure; **the outcome is not Evidence, not a Finding and not a
Verdict**, and it never satisfies an obligation of `required_evidence`.
Classifying an outcome belongs to a later epic.

- **Scope.** The Gate reads `change_id`, `revision`, `inventory_version` and
  `inventory_sha256` from `impact.json` and never re-derives the footprint, the
  Affected points or the Required evidence. An absent or inconsistent impact
  record stops the step with `PROFILE_GATE_UNSCOPED`; nothing is written.
- **Work tree.** The commands run over the current work tree, so it must be the
  Analyzed revision: `HEAD` equal to `revision` and no tracked file modified
  (staged or not; untracked files and the records directory are ignored). A
  tracked file flagged assume-unchanged or skip-worktree (a sparse checkout)
  is refused too, since `git status` cannot see an edit to it. Untracked files
  can still affect a command (an unadded module, an untracked `ruff.toml`);
  the Gate does not look at them. The tree is checked again after the commands
  ran: one that modified a tracked file stops the step with
  `PROFILE_GATE_UNSCOPED` and nothing is written.
  Otherwise the step stops with `PROFILE_GATE_UNSCOPED` and nothing is written,
  so an exit code is never attributed to a revision it was not computed over.
- **Commands.** The list is `GATE_COMMANDS` in `config.py` (default
  `ruff check .`, `ruff format --check .`, `mypy .`, `pytest -q`), never in a
  tool. Every argv[0] must be a bare name in `GATE_EXECUTABLES`; otherwise
  config loading refuses with `PROFILE_GATE_COMMAND_INVALID` and nothing is
  written. Because every tool loads the config first, an invalid Gate list also
  refuses `preflight` and the Story 2.x steps; `verify-change` reports it at
  `preflight`. Every executable must also resolve to an absolute path on
  `PATH` before anything is written, or the step stops with
  `PROFILE_GATE_COMMAND_INVALID`. Commands run in the repository root with no
  shell, `GIT_*` removed from the environment, stdin closed and a timeout. The
  rest of the environment is inherited, as are the tools' own option variables
  (for example `PYTEST_ADDOPTS`). The kit makes no network call of its own.
- **Budget.** `GATE_TIMEOUT_SECONDS` per command and an optional
  `GATE_TOTAL_TIMEOUT_SECONDS` for the whole step (`None` disables it), both
  independent of any Review budget. A command that overruns is killed with its
  process group and recorded `timed_out: true`, `exit_code: null`. Once the
  total budget is spent, the commands left are recorded the same way without
  running. Neither case aborts the step. The workflow sets no step `timeout:`:
  the bound on the Gate is this budget (the core does not enforce a step
  timeout on a synchronous tool).
- **Record.** `.beddel-profile/records/changes/<change_id>/revisions/<sha>/gate.json`
  (canonical JSON, schema `profile-dev/gate-outcome/1`) holds exactly `schema`,
  `change_id`, `revision`, `inventory_version`, `inventory_sha256`, `status`,
  `commands` (`name`, `argv`, `exit_code`, `timed_out`) and `gate_ref`.
  `status` is `completed`: when the kit could not run the Gate at all, nothing
  is written and a `ProfileError` is raised instead. `exit_code` is `null`
  exactly when the command timed out, and negative (`-N`) when it was killed by
  signal N. Command names are `<NN>-<executable>`.
- **Raw output.** Each attempt stores `gate-output/<attempt>/<name>.stdout.txt`
  and `.stderr.txt` (UTF-8, undecodable bytes replaced, never parsed). Attempts
  are numbered from 1 and are append-only. The first run creates `gate.json`; a
  re-run adds the next attempt and repoints `gate.json` and its `gate_ref` at it
  with a scratch file and `os.replace`, leaving every earlier attempt untouched.
  Two overlapping runs are not ordered: the last one to finish names its
  attempt.

## Review (Story 3.2)

`review` (`profile_run_review`) is the last step of `verify-change`. It hands an
external reviewer the derived set that `impact.json` already holds and the
`base..revision` diff, and records an **operational outcome**: `completed`,
`timed_out` or `errored`. **The outcome is not Evidence, not a Finding, not a
Pendency and not a Verdict**; it never satisfies an obligation of
`required_evidence`. The reviewer's text is stored and never parsed here.

- **Scope.** The prompt is built only from `impact.json` (`change_id`, `base`,
  `revision`, the inventory identity, `footprint`, `affected_points`,
  `required_evidence`) and the committed diff `base..revision` (through
  `_io.py`, cut at 64000 bytes with a visible marker). Nothing is re-derived
  and the work tree is not read. The diff is rendered inside the kit from git
  plumbing object reads (`git diff-tree --raw` lists per-path changes,
  `git cat-file blob <oid>` reads each side's bytes) and stdlib `difflib`
  formats the unified-diff hunks. No git configuration scope can reach this
  path — not the system, global, XDG, repo `.git/config`, `.gitattributes`,
  any diff driver, nor the repository's own `.git/info/attributes` — so the
  diff is deterministic by construction: byte-identical for the same Change,
  revision and snapshot regardless of git configuration, attributes or work
  tree. The kit owns the binary rule: a path is treated as binary when its
  content contains a NUL byte **anywhere** (not just the first 8000 bytes) or
  exceeds 1 MiB; binary paths render as `Binary files a/<path> and b/<path>
  differ` with no bytes. Unified-diff hunk headers carry **no function-name
  text** after `@@` — funcname patterns are git configuration and would
  reintroduce the config surface. The 64000-byte cap is applied **after**
  UTF-8 encoding (a byte cut); a NUL that survives to the cut point becomes
  U+FFFD, keeping the prompt argv-safe. An absent or inconsistent impact
  record stops the step with `PROFILE_REVIEW_UNSCOPED`; nothing is written.
- **Route.** `REVIEW_AGENT` (default `kiro`) names the route, `REVIEW_MODEL`
  (default `claude-opus-4.5`) the model and `REVIEW_TIMEOUT_SECONDS` (default
  900) its own budget, independent of the Gate budgets; all three live in
  `config.py`, never in a tool. The adapter is obtained only through
  `_adapters.get_review_adapter`, a static kit-local map (no core discovery);
  an unknown `REVIEW_AGENT` stops with `PROFILE_REVIEW_UNSCOPED`. The call is
  `execute(prompt, model=REVIEW_MODEL, sandbox="read-only", tools=None)`.
- **Authentication.** The kit neither authenticates nor installs. The route
  runs in the already-authenticated SSO/OAuth session of its CLI: no `api_key`
  is passed, and an ambient `KIRO_API_KEY` is refused with
  `PROFILE_REVIEW_UNSCOPED` (it would make the route run headless and ignore
  the sandbox). The binary is located and handed over explicitly, so the
  adapter's auto-install never runs; a missing binary or route is recorded as
  `errored`.
- **Outcome.** The adapter's own timeout is recorded as `timed_out`; any other
  adapter error, or a failure to start the route, as `errored` with its
  `error_code`. Neither raises. A step timeout is set in the workflow
  (`timeout: 960`) because the core bounds an asynchronous tool at 60 seconds
  by default; keep it above `REVIEW_TIMEOUT_SECONDS` plus 30.
- **Record.** `.beddel-profile/records/changes/<change_id>/revisions/<sha>/review.json`
  (canonical JSON, schema `profile-dev/review-outcome/1`) holds exactly
  `schema`, `change_id`, `revision`, `inventory_version`, `inventory_sha256`,
  `agent`, `model`, `status`, `review_ref` and, only when `status` is not
  `completed`, `error_code`. The raw text of each attempt is stored at
  `review-output/<attempt>.txt` (UTF-8, undecodable bytes replaced, empty when
  the review did not complete), numbered from 1 and append-only. The first run
  creates `review.json`; a re-run adds the next attempt and repoints
  `review.json` at it, leaving earlier attempts untouched.
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
