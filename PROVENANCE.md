# Provenance — v0.1-mvp public baseline migration

## Source

All files under this migration were imported from a verified, authentic
Git repository containing the original `v0.1-mvp` AutoCode source,
produced in an earlier Claude chat session and exported by the user as a
`.zip` (with full `.git/` history intact).

Verified before migration, in this order:

1. `git fsck --full` — no corruption; only harmless dangling-tag objects.
2. `git rev-list -n 1 v0.1-mvp` == `git rev-parse e0f3d36` — the
   `v0.1-mvp` tag points exactly to the commit `STATUS.md` names as the
   frozen reference point.
3. `bash run_all.sh` executed, unmodified, end to end: all **56 golden
   tests** (11 precedence + 14 rule-matcher + 19 canUseTool-adapter + 12
   TTL/capability) and all **4 `listapp` tests** passed. 60/60 total.
4. `can_use_tool_adapter.py` and `precedence.py` in this source were
   byte-identical to the copies already present in `ReinKam/AutoCode`
   (shared earlier via chat artifact). `govern.py` differed on one line
   — see below.
5. `listapp/_autocode/ruleset.json` (7 rules, `0.4.0-listapp`) extends
   `autocode/policy_engine/reference_ruleset.json` (5 rules, `0.3.4`) by
   exactly 2 rules, matching the top-level `README.md`'s description of
   `listapp`'s ruleset.

Test results demonstrate that these 60 scenarios behave as specified.
They do not prove the absence of defects outside that coverage.

## Historical note: `govern.py`

The canonical `govern.py` imported from historical commit `e0f3d36`
already uses the portable, repository-relative path:

```python
AUTOCODE_ENGINE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "autocode", "policy_engine")
)
```

An earlier copy of `govern.py` shared in a chat conversation (and
previously committed to `ReinKam/AutoCode`) contained a sandbox-specific
absolute path instead:

```python
AUTOCODE_ENGINE_PATH = "/mnt/user-data/outputs/autocode/policy_engine"
```

That copy was a transient presentation artifact from the chat sandbox
environment, not the canonical `v0.1-mvp` source. This migration replaces
it with the canonical, portable version. This is not a new change made
during migration — it is the source version being restored.

## What this migration does not include

Per `README.md`'s "Known gap" note (now resolved by this migration) and
per ADR 0002: this migration does not touch `admission/`,
`.github/workflows/admission-claude-agent-sdk.yml`, `CLAUDE.md`, or
anything related to the Claude Agent SDK admission work. Those are
independent of the `v0.1-mvp` core and are unaffected by this migration.
