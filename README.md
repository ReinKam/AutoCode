# AutoCode

A deterministic, policy-first control plane for autonomous software
development. See [`PITCH.md`](PITCH.md) for the one-page case and
[`STATUS.md`](STATUS.md) for current state and next steps.

## About this repository

This is a **fresh, public repository**, deliberately separate from an
earlier private `AutoCode` repository (renamed, not deleted) that was
created with the help of OpenClaw. That earlier repo has not yet been
reviewed for what it contains, so nothing from it has been carried over
here automatically — everything in this repo is either:

1. content produced directly in the chat session that built this
   admission-gate work, or
2. explicitly re-typed/copied from files the user shared as artifacts in
   that session.

### Known gap — not yet migrated

The following are referenced by imports in `autocode/policy_engine/` but
are **not present in this repo yet**, because they were never shared as
artifacts in the session that assembled this repo:

- `autocode/policy_engine/normalize.py`
- `autocode/policy_engine/rule_matcher.py`
- `autocode/policy_engine/risk_classifier_stub.py`
- `autocode/policy_engine/canonical_hash.py`
- `autocode/policy_engine/audit_log.py`
- `autocode/policy_engine/ttl_policy.py`
- `listapp/_autocode/ruleset.json`
- `listapp/_autocode/audit_log.jsonl`
- the `listapp/` application itself (`app.py`, `db.py`, `auth/`, `tests/`)
- the 56 golden tests + demo script referenced in `STATUS.md`
- `run_all.sh`

These presumably exist in the renamed old repo or on the user's machine.
**Do not assume they match what's described in `STATUS.md`/`PITCH.md`
until they've actually been copied in and diffed against that
description.** Treat this repo as `admission/` + the ADRs + the two files
needed to understand the governance contract (`can_use_tool_adapter.py`,
`precedence.py`, `govern.py`) until the rest is deliberately migrated.

## Layout

```text
PITCH.md, STATUS.md          Project narrative and current state
decisions/                    ADRs — durable architectural decisions
autocode/policy_engine/       Partial: only the two modules shared so far
listapp/_autocode/            Partial: only govern.py shared so far
admission/claude-agent-sdk/   ADR 0002 Admission Gate 0 evidence for the
                               Claude Agent SDK dependency — admission
                               note (living document) + test harness
.github/workflows/
  ci.yml                       No secrets. Static checks only (compile,
                               0.10a, pinned-version/hash verification).
  admission-claude-agent-sdk.yml
                               Manual-only (workflow_dispatch). Runs the
                               authenticated Gate 0 tests (0.1-0.9, 0.10b)
                               against the pinned SDK/CLI. Requires the
                               ANTHROPIC_API_KEY secret in the
                               `claude-sdk-admission` environment.
```

## Setup for the admission workflow

1. Repo Settings -> Environments -> New environment -> name it
   `claude-sdk-admission`.
2. Add required reviewers on that environment (available on GitHub Free
   for public repositories) so the workflow pauses for a manual approval
   before it can read the secret.
3. Add an environment secret `ANTHROPIC_API_KEY` scoped to that
   environment only (not a bare repository secret).
4. Run the workflow manually from the Actions tab, or `gh workflow run
   admission-claude-agent-sdk.yml`.
5. After a run, review the uploaded artifact, then commit a sanitized
   evidence file into `admission/claude-agent-sdk/admission_note.md`
   yourself — the workflow has `contents: read` only and cannot commit on
   its own.
