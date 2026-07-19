# tools-git-kit

Typed async Git operations for Beddel workflows.

## Overview

`tools-git-kit` provides 10 typed async Git operations that wrap the `git` CLI via `asyncio.create_subprocess_exec`. No Python git libraries are used — only `git` on PATH.

## Tools

| Tool | Description |
|------|-------------|
| `git_status` | Check worktree status (clean/dirty, modified files, ahead/behind) |
| `git_branch_create` | Create and checkout a new branch |
| `git_branch_current` | Get current branch name and SHA |
| `git_commit` | Stage specific files and commit with message |
| `git_push` | Push branch to remote |
| `git_merge` | Merge a branch into current |
| `git_diff_stat` | Get diff statistics between two refs |
| `git_fetch` | Fetch from remote with optional prune |
| `git_tag_create` | Create annotated tag and optionally push |
| `git_branch_delete` | Delete branch locally and optionally on remote |

## Key Design Decisions

- **Async-native**: All tools use `asyncio.create_subprocess_exec`
- **Explicit staging only**: `git_commit` NEVER uses `git add .` — files must be listed
- **Timeout protection**: 120s for local ops, 300s for network ops (push, fetch)
- **Structured output**: Every tool returns a typed dict
- **Branch name validation**: Regex `^[a-zA-Z0-9/_.-]+$` prevents injection

## Prerequisites

- `git` CLI on PATH
- Python 3.11+
- `beddel` SDK installed (provides `@beddel_tool` decorator)

## Usage

```python
from beddel_tools_git import git_status, git_commit, git_push

status = await git_status(cwd="/path/to/repo")
if not status["clean"]:
    await git_commit(
        files=["src/main.py", "tests/test_main.py"],
        message="feat: add new feature",
        cwd="/path/to/repo",
    )
    await git_push(cwd="/path/to/repo", set_upstream=True)
```

## Testing

```bash
cd repo/kits/tools-git-kit
pytest
```

Tests use real temporary git repos (no mocking).
