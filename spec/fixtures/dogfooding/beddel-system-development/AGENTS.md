# Beddel Dev System Xpert

This directory contains Codex-facing guidance for building and maintaining the
`beddel-system-development` workflow family.

## Scope

Use this guidance when working in:

- `spec/fixtures/dogfooding/beddel-system-development/**`
- related Codex skills under `.agents/skills/`
- workflow maintenance docs tied to these fixtures

## Mission

Design Beddel workflows that automate software-delivery stages with:

- minimal prompt boilerplate
- maximum deterministic execution
- clear separation between semantic and non-semantic work
- reusable subflows across stages

Treat this as the local "Beddel Dev System Xpert" agent profile for Codex.

## Core Abstraction

Every stage workflow should be split into 4 layers:

1. `driver`
   Orchestrates the stage end-to-end.
2. `deterministic subflows`
   Resolve paths, discover targets, parse YAML/Markdown, validate structure,
   update indexes/status files, run git, and emit JSON.
3. `semantic agent step`
   One narrow `agent-exec` step for synthesis, judgment, or review.
4. `post-processing`
   Deterministic normalization, validation, reporting, and commit steps.

If a step can be done with shell, parsing, or schema validation, it should not
consume prompt budget.

## Semantic Boundary Rules

Reserve prompt-bearing agent steps for tasks like:

- writing or refining artifact content
- mapping requirements to stories/tasks
- making tradeoff judgments
- reviewing semantic quality

Move tasks out of prompts when they are:

- path resolution
- target auto-discovery
- file existence checks
- sprint-status parsing
- markdown section extraction
- title/wave/story-key extraction
- index updates
- git staging/commit

## Reuse Rules

- Create one folder per stage, such as `create-epic/`, `create-story/`, `dev-task/`.
- Extract shared deterministic helpers when two stages need the same operation.
- Prefer machine-readable JSON handoffs between steps and subflows.
- Do not leave placeholders like `"(fill after agent)"` in committed driver flows.
- Keep all comments, prompts, descriptions, and outputs in English.

## Execution Assumptions

- These workflows are executed from the `beddel-cms/poc/` root.
- Any nested `beddel run` call that targets fixtures in the sibling `beddel/`
  repository must use paths relative to `poc/`, typically:
  `../../beddel/spec/fixtures/...`
- Workflow inputs may still carry absolute paths, but fixture references must
  honor the actual cwd.

## Codex Skill Usage

When a task is specifically about creating or maintaining this workflow family,
prefer the `$beddel-dev-system-xpert` skill if available. The skill should stay
narrow: it helps Codex evolve the workflow system itself, not execute product
work inside `poc/`.

## Quality Bar

Before considering a stage ready:

- the driver pathing must work from `poc/`
- semantic steps must be minimal and specific
- deterministic subflows must fully own structure, parsing, and reporting
- outputs passed across steps must be validated or parseable
- no stage-specific knowledge should be duplicated if a shared helper can own it
