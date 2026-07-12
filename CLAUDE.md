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
  be undone easily? This includes: direct `git push` or merge to `main`
  or any protected/release/canonical branch, changing GitHub repo/
  environment settings (secrets, protection rules, branch rules),
  triggering `admission-claude-agent-sdk.yml` (it spends real, metered
  API credits), deleting files or branches, force-pushing or rewriting
  published history, creating or moving tags, and editing
  `decisions/*.md` (ADRs) or `ruleset.json`/policy-engine code without
  the change having been explicitly discussed first.

### Job #1 — permitted within an explicitly authorized task branch

- Creating, committing to, and pushing a dedicated task branch other
  than `main`, when the human has explicitly authorized both:
  1. the exact branch name; and
  2. the concrete task and expected deliverables for that branch.

  The authorization applies only to the named branch and the named task.
  It expires when the task is completed or when the branch is merged,
  closed, abandoned, or replaced. It does not create standing permission
  for other branches, later tasks, materially expanded scope, or work
  continued in a new session without the authorization being present and
  still `active` in the "Active task-branch authorizations" table below.

  This permission covers ordinary, reversible commits and non-forced
  pushes to the named task branch. It does not cover merging,
  force-pushing, rewriting published history, deleting the remote
  branch, creating or moving tags, changing branch protection, or
  publishing a canonical baseline.

### Job #2 — explicit human approval required (in addition to the list above)

- Any direct `git push` or merge to `main`, or to any branch designated
  as protected, release-bearing, or canonical.
- Force-pushing or rewriting published history on any remote branch.
- Deleting a remote branch.
- Creating, moving, or deleting release tags.
- Changing branch-protection or release-protection rules.
- Publishing or designating a new canonical baseline.
- Expanding a previously authorized task branch beyond its explicitly
  named task or expected deliverables.

## Active task-branch authorizations

Claude Code: check this table before acting on any non-`main` branch.
Update the `Status` column to `completed`, `merged`, or `abandoned` when
the task ends — do not leave a finished authorization marked `active`.

| Branch | Task | Authorized | Status |
|---|---|---|---|
| `migration/v0.1-mvp-public-baseline` | Import the verified `v0.1-mvp` source from historical commit `e0f3d36`; add provenance and the historical note on the canonical, portable `govern.py`; run all 56 golden tests and 4 listapp tests; replace the `ci.yml` placeholder with permanent, secret-free execution of those tests; push the branch and report results. | 2026-07-11 | active |

## Rule

Job #1 actions (including authorized task-branch work above): proceed
directly, no confirmation round-trip needed for each one.

Job #2 actions: **stop and ask first**, every time, even if a similar
action was approved earlier in the session, and even on an authorized
task branch once the action falls outside that branch's named task or
into the force-push/merge/tag/deletion list above. Do not treat one
approval as standing permission for future, similar actions — this
mirrors the project's own `HilApproval` semantics in
`autocode/policy_engine/` (`previous_decision_id` links a new decision to
an old one; it never silently extends it).

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
- Test results prove that the covered scenarios behave as specified —
  56 golden tests + 4 listapp tests, or a specific admission target-test.
  They do not prove the absence of defects outside that coverage. Do not
  phrase results more strongly than this.
