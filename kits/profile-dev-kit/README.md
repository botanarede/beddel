# profile-dev-kit

Development profile kit for Beddel. It provides the entry workflow
`verify-change` and a fail-closed preflight (`profile_preflight`) that checks
the target path is a Git work tree, the gate executables resolve on `PATH`, and
the required environment keys are present (key names only, never values).

Status: Story 5.2. Entry workflows `verify-change`, `read-report`,
`ratify-inventory`, `declare-non-applicability`, `record-approval-decision`,
`approve-change` and `read-approval`; tools `profile_preflight`,
`profile_ratify_inventory`, `profile_bind_inventory`, `profile_record_change`,
`profile_derive_impact`, `profile_open_attempt`, `profile_run_gate`,
`profile_run_review`, `profile_capture_evidence`, `profile_record_report`,
`profile_read_report`, `profile_declare_non_applicability`,
`profile_record_approval_decision`, `profile_approve_change` and
`profile_read_approval`.

## Layout

```
kit.yaml                         manifest (documentation-only config block)
python/beddel_profile_dev/       Python module (tools, config)
python/beddel_profile_dev/tools/approval.py
                                 Approval verification, persistence and read-back
python/beddel_profile_dev/tools/approval_decision.py
                                 Approval decision transport
workflows/                       entry workflows, including
                                 record-approval-decision and read-approval
tests/                           kit tests (no network, no real credential)
```

## Configuration

The runtime source of `GATE_EXECUTABLES`, `REQUIRED_ENV_KEYS`, `INVENTORY_DIR`,
`RECORDS_DIR`, `GATE_COMMANDS`, `GATE_TIMEOUT_SECONDS`,
`GATE_TOTAL_TIMEOUT_SECONDS`, `REVIEW_AGENT`, `REVIEW_MODEL` and
`REVIEW_TIMEOUT_SECONDS` is `python/beddel_profile_dev/config.py`, resolved relative
to the kit root. `RECORDS_DIR` is resolved under `Path.home()/".config"/"beddel"`
and separated by a SHA-256 key of the repository's Git common directory. The
`config:` block in `kit.yaml` only documents the same values; the core does not
read it. Missing or malformed config raises; it never degrades to empty lists.

## Inventory and ratification (Story 2.2)

An inventory version lives in the verified repository at
`.beddel-profile/inventory/<version>.yaml`: a mapping with exactly `version`
(equal to the file stem), `classes` (`{id, kind: gate|review}`), `components`
(`{id, kind: component|shared_contract, path}`), `criteria`
(`{id, description}` or `{id, description, blocking}`) and `obligations`
(`{class, affected_point, criterion}`). A criterion's optional `blocking` must
be a YAML boolean. It is copied into the bound snapshot only when defined;
older criteria keep the byte-identical snapshot shape.
Ids match `^[a-z0-9][a-z0-9._-]{0,63}$`; quote ids that YAML would read as
numbers. Unknown keys are rejected.

- `ratify-inventory` (inputs `repo_path`, `inventory_version`, `actor`) writes
  `<version>.ratification.yaml` next to the version file, create-only. The
  maintainer commits it: that commit is the human act; the tool is transport.
  A ratified version is immutable; a change is a new version.
- `verify-change` (inputs `repo_path`, `change_id`, `base`, `revision`,
  `inventory_version`) runs `preflight`, `change`, `bind_inventory`, `impact`,
  `attempt`, `gate`, `review`, `evidence` and `report`. `read-report` (inputs
  `repo_path`, `change_id`) returns the latest Report and its append-only history
  without running verification or writing records. `bind_inventory` reads the
  version and its ratification from the tree of `revision`, validates identity
  formation and resolution, and either records one integrity block
  (`PROFILE_INVENTORY_INTEGRITY_BLOCK`) or writes `binding.json` and the
  canonical `snapshot.json` under the setup-relative records root (local files,
  never committed by the kit). An unratified version stops with
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
  Records live under the setup-relative records root, separated by the stable
  repository key, and the legacy repository-local records are not read.
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

`gate` (`profile_run_gate`) is the sixth step of `verify-change`. It runs the
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
- **Record.** The revision-level pointer is stored under the setup-relative
  records root at `changes/<change_id>/revisions/<sha>/gate.json`
  (canonical JSON, schema `profile-dev/gate-outcome/1`). The attempt-bound
  record is `attempts/<n>/gate.json` with schema
  `profile-dev/attempt-gate-outcome/1` plus an `attempt` field (the
  VerificationAttempt ordinal) and an `output_attempt` field (the
  `gate-output/<k>` ordinal). Both carry the same 3.1 outcome fields; the
  pointer omits `attempt` and `output_attempt`.
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

`review` (`profile_run_review`) is the seventh step of `verify-change`. It hands an
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
- **Record.** The revision-level pointer is stored under the setup-relative
  records root at `changes/<change_id>/revisions/<sha>/review.json`
  (canonical JSON, schema `profile-dev/review-outcome/1`). The attempt-bound
  record is `attempts/<n>/review.json` with schema
  `profile-dev/attempt-review-outcome/1` plus an `attempt` field (the
  VerificationAttempt ordinal) and an `output_attempt` field (the
  `review-output/<k>.txt` ordinal); the pointer omits both. The raw text
  remains at `review-output/<k>.txt`; a timeout or error stores an empty output
  but produces no Review Evidence.
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

## VerificationAttempt and Evidence (Story 3.3)

`attempt` (`profile_open_attempt`) runs after Impact and before Gate. It claims
an ordinal with exclusive directory creation and persists the complete immutable
scope under `changes/<change_id>/revisions/<sha>/attempts/<n>/attempt.json`.
The scope includes the Change, revision, canonical snapshot and sorted
Requirement ID constituents. A later run claims a new ordinal; it never edits
an earlier attempt.

Gate and Review receive the attempt ordinal and write create-only bound outcomes
under `attempts/<n>/gate.json` and `attempts/<n>/review.json`. Revision-level
`gate.json` and `review.json` remain mutable latest pointers with their existing
Story 3.1 and 3.2 shapes. `evidence` (`profile_capture_evidence`) reads only the
bound outcomes and writes one create-only file per matching Requirement ID. Gate
Evidence preserves its commands and reference. Completed Review Evidence keeps
the reviewer reference and the SHA-256 of non-blank stored output. Timed-out,
errored or blank Reviews produce no Review Evidence.

## Verification Report (Stories 4.1, 4.3, 4.2 and 4.4)

`report` (`profile_record_report`) runs after Evidence and appends one canonical
JSON Report under `changes/<change_id>/report/<n>.json`. New records use schema
`profile-dev/verification-report/4`; `read-report` accepts `/1`, `/2`, `/3` and
`/4` records and returns earlier records unchanged; stored records are never
rewritten. It selects only the greatest
persisted attempt ordinal for the Change and revision. A valid attempt links the
seven Report items to the recorded snapshot, Impact and validated Evidence; a
missing or malformed latest attempt is recorded as indeterminate. Reports are
create-only and never rewrite earlier records.

The ratified criterion may define `blocking: true` or `blocking: false`. The
bound snapshot carries that field only when it was defined, preserving the
legacy snapshot bytes otherwise. Each Finding receives `classification`:
`blocking`, `non_blocking` or `unclassified`. An unknown association or a
criterion without a blocking definition is `unclassified`.

The top-level `assessments` list contains one state for every Requirement ID,
sorted by class, Affected point and criterion. States are `no_divergence`,
`divergent`, `indeterminate` or `not_assessed`. A gate non-zero exit produces a
Finding between implementation and validation; a timeout or null exit makes
that assessment indeterminate. Review Findings come from the verified Review
output only. Each Finding records its source, Requirement association (or
`unknown`), the two disagreeing constituents and a detail containing the gate
or Review reference.

The Report has exactly one `verdict`: `consistent` when `pendencies` is absent,
or `has pendency` otherwise. A pendency entry has the shape
`{reason, class, affected_point, criterion, kind}`. Its `reason` is one of
`attempt_not_valid`, `evidence_unrecorded`, `assessment_indeterminate`,
`finding_blocking`, `finding_unclassified` or
`earlier_finding_not_reverified`. Finding entries also carry `finding_index`.
The top-level `reverification` entry is either `{"status": "not_applicable"}`
or `{"status": "recorded", "earlier_revision": R, "links": [...]}`.
Each link has exactly `report_ref`, `finding_index`, `association`, `class`,
`affected_point`, `criterion`, `kind`, `state`, `result` and `reason`; it has no
separate Requirement ID field. `result` is `resolved`, `still_divergent` or
`not_reverified`. A `not_reverified` link has reason `indeterminate` or
`outside_scope`; other results have a null reason. A not-reverified link adds an
`earlier_finding_not_reverified` Pendency with its `link_index`. The
`profile_record_report` tool result includes the Re-verification status under
`reverification`. Change-level Pendencies use `null` for the constituent
fields. Entries are emitted in deterministic list order. A non-blocking Finding
creates no pendency in its own revision, and a corrected revision records its
Re-verification links in the top-level entry.

The `pendencies` item is `absent` for an empty list and `present` otherwise.
A malformed earlier Report, including any accepted schema, stops
`record-report` with `PROFILE_REPOSITORY_INVALID` before it writes a new
record. New Reports list earlier Report records in `reads` with their
references and SHA-256 digests.

The Review prompt requires exactly one UTF-8 JSON block between
`BEDDEL-ASSESSMENT-BEGIN` and `BEDDEL-ASSESSMENT-END`. Its schema is
`profile-dev/review-assessment/1` with `assessments` for the review-class IDs
and `unassociated` entries for divergences with no matching ID. The stored
output is parsed only after its SHA-256 matches Review Evidence. An unreadable,
missing or duplicated assessment leaves the affected Review assessment
indeterminate and creates no Finding from that entry.

`read-report` invokes `profile_read_report` with `repo_path` and `change_id`.
It returns the latest Report plus every stored record in ordinal order, each
with its reference, SHA-256 and content. It performs no Gate, Review or write.
Until a Report exists it returns `report: null` and an empty `history`.

A Finding has `source`, `association`, `class`, `affected_point`, `criterion`,
`kind`, `between`, `detail` and `classification`. `association` is
`requirement` when the entry names a Requirement ID, otherwise `unknown`; `kind`
is the Requirement kind or `null` for an unknown association. Each `between`
value contains two distinct members of `specification`, `implementation`,
`validation` and `affected_point`.

The `divergences` item is `present` when at least one Finding exists. It is
`absent` only when the assessment state list is non-empty and every state is
`no_divergence`; otherwise it is `not_assessed`. A Review assessment block with
extra keys, duplicate JSON keys, invalid values or a Markdown code fence inside
the markers is unreadable. Marker lines may carry trailing whitespace only.
Unreadable blocks produce no Review Findings and leave applicable Review states
indeterminate.

## Change Approval (Stories 5.1 and 5.2)

Approval has two human-controlled steps. `record-approval-decision` invokes
`profile_record_approval_decision` with `repo_path`, `change_id`, `revision`
and `actor`. It writes one YAML decision under
`.beddel-profile/approvals/<change_id>/<report-ordinal>.yaml` with exactly
these fields:

- `schema: profile-dev/approval-decision/1`
- `change_id`, `revision`, `report`, `report_sha256`
- `approved_by`, `approved_at`

All values must remain quoted YAML strings. The tool never commits the file;
the maintainer commits it so its Git history is auditable. The repository must
not gitignore `.beddel-profile/`, or the decision cannot be committed and
verified. After committing, obtain the full decision commit SHA with
`git rev-parse HEAD` and pass that value as `decision_commit`.

`approve-change` invokes `profile_approve_change` with `repo_path`, `change_id`,
`revision`, `actor` and `decision_commit`. It revalidates the recorded Change
and revision link, the latest `/4` Report, its authoritative attempt, every
`reads` digest and the Verdict derived by the same canonical use case as
`profile_record_report`. It then reads the decision only from the named commit,
checks that the commit is reachable from `HEAD`, and writes one create-only
`changes/<change_id>/approval.json` record with exactly these fields:

- `schema: profile-dev/approval/1`
- `change_id`, `revision`, `report`, `report_sha256`, `attempt`
- `approved_by`
- `proof: {commit, path, sha256}`

`proof.commit` is the full commit SHA resolved from `decision_commit`; `proof.path` is the
decision path; and `proof.sha256` is the decision blob digest. The input actor
must equal `approved_by`; no commit author or environment identity is copied
into the record.

`read-approval` invokes `profile_read_approval` with `repo_path` and
`change_id`. It returns the stored Approval or `null` without writing records.
The workflows are separate from `verify-change`; `verify-change` has no
Approval step.

Refusal checks run in this order. The decision transport checks
`id.invalid`, `actor.invalid`, `revision.invalid`, `change.unrecorded`,
`report.malformed`, `report.absent`, `revision.not_reported`,
`decision.exists` for a work-tree path or symlink, `history.unreadable`,
and then `decision.exists` for an index, `HEAD`-history or create-only duplicate. The Approval
use case checks `id.invalid`, `actor.invalid`, `revision.invalid`,
`approval.exists`, then `change.unrecorded`, `revision.unlinked`,
`report.malformed`, `report.absent`, `report.outdated`,
`revision.not_reported`, `attempt.superseded`, `digest.mismatch`,
`verdict.underivable`, `verdict.mismatch`, `verdict.has_pendency`,
then `decision.commit_invalid`, `decision.unreachable`, `decision.absent`,
`decision.malformed`, `decision.unsupported`, `decision.actor_invalid`,
`decision.target_mismatch`, `decision.digest_mismatch`, `actor.mismatch`, and
`approval.exists` when the create-only write finds an existing record.

Every refusal raises `PROFILE_APPROVAL_REFUSED` and writes nothing. An invalid
repository path or records root keeps `PROFILE_REPOSITORY_INVALID`.
Ratification and Approval remain separate human acts.
