# tools-github-kit

Typed async GitHub pull request operations through the machine's existing `gh`
login. The kit runs explicit `gh` argv in the supplied repository and never
stores or receives credentials.

## Tools

| Tool | Purpose |
|------|---------|
| `github_pr_create_or_reuse` | Create one open pull request or reuse the sole matching request |
| `github_pr_checks_wait` | Poll the pull request check rollup until it passes, fails, or times out |
| `github_pr_merge` | Merge one open, checked pull request with a pinned head SHA |

`github_pr_create_or_reuse` accepts a branch, base branch, story key, spec
path, Change id, and revision. It invokes `gh pr list` and, when needed,
`gh pr create --head ... --base ... --title ... --body ...`, then lists again.
The generated body contains only these references:

```text
Story: <story_key>
Spec: <spec_path>
Change: <change_id>
Revision: <revision>
```

`github_pr_checks_wait` invokes `gh pr view <number> --json
number,state,headRefOid,statusCheckRollup`. A configured check is every entry
in that rollup. Completed `SUCCESS`, `NEUTRAL`, and `SKIPPED` CheckRuns and
`SUCCESS` StatusContexts pass. Pending entries wait; all other conclusions or
states fail. An empty rollup passes only after `grace` seconds.

`github_pr_merge` first views the requested number, refuses failed or pending
checks, runs `gh pr merge <number> --<merge|squash|rebase> --match-head-commit
<head_sha>`, and verifies the resulting `MERGED` state. Results contain
structured number, URL/branch/base, check, or merge keys as appropriate.

## Errors

The kit raises `GitHubToolError`, with one of these codes:

`GITHUB_ARGUMENT_REFUSED`, `GITHUB_CLI_MISSING`, `GITHUB_CLI_FAILED`,
`GITHUB_CLI_TIMEOUT`, `GITHUB_OUTPUT_INVALID`, `GITHUB_PR_CONFLICT`,
`GITHUB_PR_AMBIGUOUS`, `GITHUB_CHECKS_PENDING`, `GITHUB_CHECKS_FAILED`,
`GITHUB_PR_NOT_OPEN`, `GITHUB_PR_MISMATCH`, and `GITHUB_MERGE_INCOMPLETE`.

## Prerequisites and testing

The machine must have `gh` installed and authenticated through its existing
`gh auth` configuration. Python 3.12+ and the Beddel SDK are required.

```bash
cd repo/kits/tools-github-kit
pytest -q
```

Tests place a fake `gh` first on `PATH`; they do not access a network or a real
repository host.
