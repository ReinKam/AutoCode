# Admission Gate 0 test harness — how to run

## Prerequisites (already pinned in `../admission_note.md`)
- `../venv/` — a Python venv with `claude-agent-sdk==0.2.116` installed
- `ANTHROPIC_API_KEY` set in your shell environment (NOT in any file in
  this repo, and never pasted into chat with Claude — set it yourself)

## Run everything
```bash
cd sdk_admission
export ANTHROPIC_API_KEY=...           # your own key, your own shell
for f in harness/test_0_*.py; do
  echo "=== $f ===" >&2
  ./venv/bin/python3 "$f"
  echo
done
```

Each script prints exactly one JSON line to stdout (the verdict); narration
goes to stderr. Redirect stdout to a file to collect machine-readable
results:

```bash
for f in harness/test_0_*.py; do
  ./venv/bin/python3 "$f" >> results.jsonl 2>>run.log
done
```

`test_0_10a_static_no_persisted_permissions.py` needs no API key and can be
run any time (already run once — see `admission_note.md`).

## After running
Paste `results.jsonl` (or the individual verdict lines) back. Each verdict's
`notes` field states its own pass criteria in plain text, so results can be
classified against Admission Gate 0 without re-deriving the criteria from
this README.

## What this does NOT cover yet
- 0.9's fully authenticated variant (only the mechanical cancellation is
  covered here)
- A `settings.json`-sourced allow rule in 0.4 (only `allowed_tools`,
  `acceptEdits`, `bypassPermissions` are exercised)
- Anything about MCP tool calls or subagent-spawned tool calls specifically
  — all tests here use the built-in `Bash` tool only
