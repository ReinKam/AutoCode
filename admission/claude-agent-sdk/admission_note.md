# Admission Note — Claude Agent SDK (`claude-agent-sdk`)

Status: **Admitted** (pinned combination below only — see "Admission decision")

This is a living evidence document per ADR 0002. It records what the
target-tests in `harness/` observed. Any future upgrade to
`claude-agent-sdk` or a change in the bundled CLI's SHA-256 invalidates
this admission and requires Gate 0 to be re-run (`ci.yml`'s
`verify-pinned-sdk-version` job enforces the version/hash check on every
push so drift is caught automatically, but re-running the *authenticated*
tests after a legitimate upgrade is a manual step — see "Re-admission
trigger" at the end of this document).

## Dependency

```text
Dependency:        claude-agent-sdk (Python)
Pinned version:    0.2.116   (pip)

Underlying CLI:     @anthropic-ai/claude-code
CLI version:        2.1.207
CLI resolution:     BUNDLED — shipped inside the claude-agent-sdk pip package
                     at claude_agent_sdk/_bundled/claude, NOT the separately
                     npm-installed copy. The SDK's _find_cli() checks the
                     bundled path first and returns it before ever falling
                     back to `shutil.which("claude")` or npm-installed
                     locations. Both copies happen to report the same
                     version string (2.1.207) in this environment, but that
                     is coincidence, not a resolution guarantee — a future
                     mismatch between a global npm install and the bundled
                     copy would silently use the bundled one unless
                     `cli_path` is passed explicitly.
CLI binary SHA-256:  85e7e988a392d859f90802ca21fb26e89d3c9ab527f5ed0b08df3955e34d5c83
CLI binary size:      259402552 bytes

Runtime pinning strategy: harness/ passes ClaudeAgentOptions(cli_path=...)
explicitly, pointing at the exact bundled binary above by absolute path, so
no ambiguity about which binary is exercised by the target-tests. ci.yml
independently re-verifies this exact SHA-256 on every push, before any
authenticated test can run.
```

## Runtime environment (authenticated Gate 0 run)

```text
Python:    3.12.13
Runner OS: Linux 6.17.0-1018-azure x86_64 (GitHub-hosted ubuntu-latest runner)
Workflow run ID: 29149642655
Commit:          3ecbfb02a61ce75f20398796be510a91d6accb7b
Triggered by:    ReinKam
Timestamp (UTC): 2026-07-11T10:42:14Z
```

## Role

Trust-bearing execution and permission-routing dependency. Its output and
failure modes determine whether a tool call reaches execution before
AutoCode's own `PolicyDecision` exists for it — this is precisely the
category ADR 0002 defines as trust-bearing.

## Documented assumptions (per Anthropic's published docs, fetched 2026-07-11)

- `PreToolUse` hooks run before permission modes, deny rules, ask rules, and
  allow rules; a hook can allow, deny, ask, or defer a call before anything
  else is evaluated.
- Any call resolved by an earlier step (allow rule, `acceptEdits`,
  `bypassPermissions`) never reaches `canUseTool`. Anthropic states this
  explicitly and recommends a `PreToolUse` hook for governance that must
  apply to every call, regardless of mode/rules.
- `permissionDecision: "ask"` on a `PreToolUse` hook routes the call to
  `canUseTool` for confirmation.
- `canUseTool` can hold the pause indefinitely; the SDK does not time it out
  on its own (a `defer` mechanism exists for very long waits, not required
  for this MVP).
- `AskUserQuestion` also triggers `canUseTool` and must be branched away
  from ordinary tool-approval handling.
- `updated_permissions` returned from `canUseTool` persists a permission
  rule so later matching calls can skip the callback entirely.

**Confirmed directly in this Gate 0 run:** the SDK self-diagnoses exactly
the shadowing risk this admission exists to check. `run.log` shows the
SDK itself emitting `CanUseToolShadowedWarning` for both the bare
`allowed_tools` and `bypassPermissions` configurations in test 0.4 — e.g.
*"can_use_tool will not be invoked: permission_mode 'bypassPermissions'
auto-approves every tool call (except explicit deny rules) before the
callback is consulted. To gate every tool call, use a PreToolUse hook
instead."* This is not just documentation; it is the running SDK actively
warning about the exact failure mode ADR 0002 was worried about — and
AutoCode's `PreToolUse` hook closed that gap in every configuration
tested (see Target-test evidence, 0.4).

## Corrected assumption (found wrong by the target-tests, in the safe direction)

The original note assumed a `PreToolUse` hook returning `{}` (documented
"no opinion, pass through") would result in `execution_count==1` when no
`can_use_tool` callback is registered, based on the docs describing `{}`
as pass-through-to-allow semantics. **Observed behavior in test 0.7,
`empty_dict_return` variant: `execution_count==0`, with `hook_calls==2`**
(the hook was invoked twice — consistent with Claude retrying after the
call was denied somewhere downstream, though the harness did not capture
enough detail to confirm the retry mechanism precisely). The actual
runtime behavior was **more conservative than the documented assumption**,
not less — i.e. the failure mode leans fail-closed here, not fail-open.
This is logged as a correction, not a defect: the original assumption was
wrong, and the real behavior is safer than what was assumed.

## Other findings from this run

- Test 0.7's malformed-hook-output variants (`missing_hookEventName`,
  `unknown_permissionDecision`, `wrong_structure`, `none_return`)
  triggered visible internal errors in the CLI's own request-handling
  layer (`ZodError`, and a Python-side `'NoneType' object has no
  attribute 'items'`) in `run.log`. This indicates the CLI performs
  schema validation on hook output and rejects malformed responses at
  that layer, rather than silently trusting them. `execution_count`
  stayed at `0` in every one of these variants. The harness cannot
  attribute individual internal error lines to individual variants with
  full certainty, since `run.log` interleaves output across the test's
  internal async operations — but the net safety property (zero
  execution across all malformed-output variants) is unambiguous.
- Harness completeness gap (not a finding about the SDK): test 0.9 never
  serialized its local `callback_returned` flag into the emitted JSON
  verdict, only referenced it in the `notes` string. The collateral
  evidence in the actual verdict (`process_outcome: "cancelled"`,
  `callback_calls: 1`, `execution_count_observed: 0`) is consistent with
  the required behavior (the callback never returned, so it could never
  have produced a false approval), but this is slightly less directly
  proven than the other tests. Worth fixing in a future harness revision;
  not treated as blocking for this admission decision.

## Target-test evidence

Full raw evidence: `evidence/results.jsonl`, `evidence/run.log`,
`evidence/environment.json` from workflow run `29149642655`
(`gate0-evidence-29149642655.zip`, downloaded and reviewed by the user,
2026-07-11).

| Test | Description | Result | Verdict |
|---|---|---|---|
| 0.1 | `ask` routes to `can_use_tool` | hook×1, callback×1, execution=0 | **PASS** |
| 0.2 | allow -> exactly one execution | hook×1, callback×1, execution=1, input matched | **PASS** |
| 0.3 | deny -> zero execution | execution=0, canary file never created | **PASS** |
| 0.4 | auto-approval paths still hit hook when present | all 3 configs (`allowed_tools`, `acceptEdits`, `bypassPermissions`), with_hook=true: hook×1, callback×1 each. with_hook=false contrast rows confirm documented bypass (hook×0, callback×0, execution=1) | **PASS** |
| 0.5 | hook exception -> zero execution | hook×1, callback never reached, execution=0 | **PASS** |
| 0.6 | hook timeout -> zero execution | timeout=3s, hook sleeps 15s, execution=0, no "woke up" event recorded (cut off before completion) | **PASS** |
| 0.7 | malformed hook output -> zero execution | all 5 variants (incl. `empty_dict_return`, see correction above): execution=0 | **PASS** |
| 0.8 | callback exception after `ask` -> zero execution | hook×1, callback×1 (raised), execution=0 | **PASS** |
| 0.9 | cancellation mid-HIL-wait -> zero execution, no false approval | callback blocked, cancelled, execution=0, callback never returned (see harness gap note above) | **PASS** |
| 0.10b | approved call #1 doesn't bypass hook/callback for call #2 | hook×2, callback×2, both calls independently routed, execution=2 (1 each) | **PASS** |
| 0.10a | static: AutoCode adapter never sets `updated_permissions` | `not_applicable_yet` — `sdk_governance.py` does not exist yet | **re-run once that file exists, before treating 0.10 as fully closed** |

## Execution constraint — resolved

The dynamic target-tests (0.1–0.9, 0.10b) required a real, authenticated
`query()`/`ClaudeSDKClient` session. This sandbox originally had no
`ANTHROPIC_API_KEY` and this Claude session does not handle API keys on
the user's behalf. The user ran the harness themselves via a manually
triggered, environment-protected GitHub Actions workflow
(`admission-claude-agent-sdk.yml`) with `ANTHROPIC_API_KEY` stored as an
environment secret on `claude-sdk-admission` (required-reviewer approval
enabled, admin bypass disabled), and provided the resulting evidence
artifact back for review. This satisfies the original constraint's intent:
the tests exercised the *actual* SDK, not a mock, with the person best
positioned to hold the credential holding it.

Two harness/infrastructure bugs surfaced and were fixed during this
process, both now in git history:

1. A truncated SHA-256 (63 instead of 64 hex characters) in this file and
   both workflow files, caught by `ci.yml`'s own verification step on the
   first push — the CI check did exactly what it was built for.
2. `common.py`'s `BUNDLED_CLI` path computation assumed a flat sandbox
   layout (`harness/` and `venv/` as siblings) and was not updated when
   the harness was relocated into the repo tree
   (`admission/claude-agent-sdk/harness/`), causing every authenticated
   test to fail before emitting a verdict on the first live run (workflow
   run `29148927847`, empty `results.jsonl`). Fixed by resolving
   `BUNDLED_CLI` three directory levels above `harness/` instead of one.

## Admission decision

**Admitted**, for exactly this pinned combination:

```text
claude-agent-sdk == 0.2.116
CLI (bundled)     == 2.1.207
CLI SHA-256       == 85e7e988a392d859f90802ca21fb26e89d3c9ab527f5ed0b08df3955e34d5c83
```

All fail-closed hard requirements (0.3, 0.5, 0.6, 0.7, 0.8, 0.9) were met
with zero unintended execution across every exercised failure path,
including a genuine internal SDK/CLI validation layer observed rejecting
malformed hook output. Every auto-approval path tested (0.4) was
successfully closed by AutoCode's `PreToolUse` hook. HIL-approval
re-evaluation (0.10b) correctly re-routes a structurally similar second
call rather than reusing the first call's approval.

**Outstanding before `sdk_governance.py` itself can be considered
admitted (not just its underlying SDK dependency):**
- Re-run 0.10a once `sdk_governance.py` exists, to close the static
  `updated_permissions` check.
- Consider adding an authenticated variant of 0.10 that also exercises a
  *non-matching* second call, to more fully characterize the boundary of
  what "structurally similar" means in the SDK's own routing logic (not
  required for this admission, since 0.10b as tested already answers the
  narrower, load-bearing question: does approval persist by default —
  no).

## Re-admission trigger

Any of the following invalidates this admission and requires re-running
the authenticated Gate 0 tests before relying on the new
version/binary/configuration:

- `claude-agent-sdk` version changes (pip)
- The bundled CLI's SHA-256 changes, even if the version string doesn't
  (`ci.yml` will fail the push automatically if this drifts unnoticed)
- A material change to `admission-claude-agent-sdk.yml`'s permission mode,
  hook configuration, or environment protection rules
- A material change to how `sdk_governance.py` (once written) constructs
  its own `PreToolUse` hook or `can_use_tool` callback
