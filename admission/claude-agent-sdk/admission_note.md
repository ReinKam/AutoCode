# Admission Note — Claude Agent SDK (`claude-agent-sdk`)

Status: **pending**

This is a living evidence document per ADR 0002. It is not a substitute for
the target-tests in `harness/` — it records what those tests observe. Do not
treat any line below as an admission decision until the "Admission decision"
section is filled with a final verdict backed by recorded evidence.

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
no ambiguity about which binary is exercised by the target-tests.
```

## Runtime environment

```text
Python:    3.12.3
Node.js:   v22.22.2 (present but not the CLI actually used — see above)
npm:       10.9.7
OS:        Ubuntu 24.04.4 LTS (Noble Numbat)
Kernel:    Linux 6.18.5 x86_64
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

## Undocumented or insufficiently specified assumptions — require target-test evidence

- Exact behavior of a `PreToolUse` hook that raises an exception.
- Exact behavior of a `PreToolUse` hook that times out.
- Exact behavior of a `PreToolUse` hook returning malformed/invalid output
  (missing `hookEventName`, unknown `permissionDecision`, `None`, `{}` in a
  context where routing was expected).
- Exact behavior when `can_use_tool` itself raises after a hook already
  returned `"ask"`.
- Reliability of `permissionDecision` enforcement across CLI versions: a
  filed, third-party-observed issue (`anthropics/claude-code#52822`)
  reports that on CLI v2.1.119, a `PreToolUse` hook returning
  `permissionDecision: "allow"` did not reliably suppress the native
  interactive permission prompt — a possible regression from v2.1.59, where
  the same case was confirmed working. Our pinned CLI is v2.1.207, a later
  version than either data point in that issue thread; whether the
  regression is present, fixed, or irrelevant at v2.1.207 is **not known**
  and must be established by our own target-tests (0.1, 0.4), not inferred
  from the issue thread. Note also the issue concerns *interactive native
  prompt suppression*, which is a related but not identical code path to
  the programmatic `PreToolUse -> canUseTool` contract this admission
  primarily depends on.
- Cancellation semantics: whether a cancelled query guarantees zero
  execution when cancellation races with a pending `canUseTool` call.
- Exact interaction between `updated_permissions` suggestions and later
  calls in the *same* session (does an approved call actually cause a
  structurally identical later call to bypass the hook, not just the
  callback?).

## Target-test evidence

| Test | Description | Status | Observed result | Artifact |
|---|---|---|---|---|
| 0.1 | `ask` routes to `can_use_tool` | pending — requires authenticated run | — | `harness/test_0_1_ask_routes.py` |
| 0.2 | allow -> exactly one execution | pending — requires authenticated run | — | `harness/test_0_2_allow_execution.py` |
| 0.3 | deny -> zero execution | pending — requires authenticated run | — | `harness/test_0_3_deny_zero_execution.py` |
| 0.4 | auto-approval paths still hit hook | pending — requires authenticated run | — | `harness/test_0_4_bypass_paths.py` |
| 0.5 | hook exception -> zero execution | pending — requires authenticated run | — | `harness/test_0_5_hook_exception.py` |
| 0.6 | hook timeout -> zero execution | pending — requires authenticated run | — | `harness/test_0_6_hook_timeout.py` |
| 0.7 | malformed hook output -> zero execution | pending — requires authenticated run | — | `harness/test_0_7_malformed_output.py` |
| 0.8 | callback exception after `"ask"` -> zero execution | pending — requires authenticated run | — | `harness/test_0_8_callback_exception.py` |
| 0.9 | cancellation mid-HIL-wait -> zero execution, auditable first decision, no false approval | pending — requires authenticated run (mechanical variant still needs a live session for `canUseTool` to ever fire) | — | `harness/test_0_9_cancellation.py` |
| 0.10a | static: AutoCode adapter never sets `updated_permissions` | **runnable now, no auth needed** | not yet run — `sdk_governance.py` doesn't exist yet | `harness/test_0_10a_static_no_persisted_permissions.py` |
| 0.10b | end-to-end: approved call doesn't let a later matching call bypass the hook/callback | pending — requires authenticated run | — | `harness/test_0_10b_e2e_no_bypass.py` |

## Execution constraint — disclosed, not worked around

Every dynamic target-test (0.1–0.9, 0.10b) requires driving a real
`query()`/`ClaudeSDKClient` session against the Anthropic API, because
`canUseTool`/`PreToolUse` only fire when Claude itself requests a tool call.
There is no way to exercise the *actual* SDK routing behavior without a
live model turn — mocking the transport would test our own mock, not the
SDK, which defeats the purpose of this admission process.

This sandbox has no `ANTHROPIC_API_KEY` configured, and per the operating
constraints on this Claude session, entering or otherwise handling API keys
on the user's behalf is out of scope regardless of who asks. The harness
below is written to be run as-is, unmodified, in an environment where
`ANTHROPIC_API_KEY` is already set (the user's own machine, CI, etc.). Each
script prints one machine-readable JSON verdict line; running all of them
and pasting the output back is sufficient to complete this admission note.

## Harness build status

- `harness/` built for tests 0.1–0.9, 0.10a, 0.10b.
- All scripts pass `py_compile`; every SDK symbol they import
  (`ClaudeAgentOptions`, `ClaudeSDKClient`, `HookMatcher`,
  `PermissionResultAllow`, `PermissionResultDeny`, and the `can_use_tool` /
  `hooks` / `cli_path` fields on `ClaudeAgentOptions`) was confirmed present
  on the pinned `claude-agent-sdk==0.2.116` install via `inspect`, not
  assumed from documentation.
- 0.10a (the only auth-free test) has been run once: result
  `not_applicable_yet`, correctly, since `sdk_governance.py` does not exist
  yet. This is the expected/correct output at this stage, not evidence
  toward admission.
- 0.1–0.9 and 0.10b have NOT been executed. They require
  `ANTHROPIC_API_KEY`, which this sandbox does not have and which this
  Claude session will not accept from the user in chat or otherwise handle
  on their behalf (credential handling is out of scope regardless of who
  asks). See `harness/README.md` for how to run them.

## Admission decision

**pending** — no dynamic evidence collected yet. Blocked on an authenticated
run of `harness/test_0_1_*.py` through `test_0_9_*.py` and
`test_0_10b_*.py`.
