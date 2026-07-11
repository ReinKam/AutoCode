# CLAUDE.md — operating boundary for Claude Code in this repository

Read `STATUS.md` and `decisions/` before proposing or making changes.
This file governs *how* you (Claude Code) operate in this specific repo,
not the project's architecture — that lives in `STATUS.md`/`decisions/`.

## The Job #1 / Job #2 boundary

This repo distinguishes two kinds of judgment, established during the
project's own design work (see `STATUS.md`, "Claude Code as the interim
execution backend"):

- **Job #1 — technical/mechanical.** Is an action reversible, low-risk,
  and already agreed in the conversation? Reading files, running
  read-only commands (`git status`, `git log`, `git diff`, tests), and
  committing changes whose content has already been explicitly agreed
  with the human in the current conversation.
- **Job #2 — product/architectural judgment, or high-stakes/irreversible
  actions.** Does this decide what the project should do, or can it not
  be undone easily? This includes: `git push` to `main` (or any shared
  branch), changing GitHub repo/environment settings (secrets, protection
  rules, branch rules), triggering `admission-claude-agent-sdk.yml` (it
  spends real, metered API credits), deleting files or branches, editing
  `decisions/*.md` (ADRs) or `ruleset.json`/policy-engine code without
  the change having been explicitly discussed first.

## Rule

Job #1 actions: proceed directly, no confirmation round-trip needed for
each one.

Job #2 actions: **stop and ask first**, every time, even if a similar
action was approved earlier in the session. Do not treat one approval as
standing permission for future, similar actions — this mirrors the
project's own `HilApproval` semantics in `autocode/policy_engine/`
(`previous_decision_id` links a new decision to an old one; it never
silently extends it).

## Project-specific conventions

- "proves/proven" is reserved for claims backed by a specific golden test
  or, for the admission-gate work, a specific target-test result recorded
  in `admission/claude-agent-sdk/admission_note.md`. Use
  "demonstrates/validates" otherwise.
- Any change to `ruleset.json`, `precedence.py`, or the audit-log format
  is a Job #2 action and needs an ADR, per the pattern in `decisions/`.
- Commit messages for anything touching `admission/` or `.github/
  workflows/` should state what evidence or decision motivated the
  change, not just what changed mechanically — future readers need the
  "why," per the discipline already established in this repo's git
  history.
