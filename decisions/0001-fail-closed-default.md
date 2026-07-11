# ADR 0001 — Fail-closed default for unmatched actions

## Status
Accepted

## Context
Early in the Policy Engine's design, `resolve()` returned `allow` when
an `ActionProposal` matched zero rules in the ruleset (`NO_RULES_MATCHED`
→ `allow`). This is the common default in most systems: permit unless
explicitly forbidden. It meant any action type or path not yet covered
by a rule passed through automatically — including, at one point,
`run_command` in general, since no rule governed it at all until one was
added specifically to close that gap.

## Decision
`resolve()`'s default for zero matched rules is `require_hil`, not
`allow`. This is configured via `Ruleset.precedence.default_effect_on_no_match`,
which the schema forbids from ever being set to `allow` — so the
fail-closed posture is structural, not just today's convention.

The only way an action is permitted by default is an **explicit** `allow`
rule (e.g. `READ_ONLY_ACTIONS_ALLOWED`, `LISTAPP_SOURCE_WRITE_ALLOWED`).
Coverage gaps in the ruleset show up as `require_hil`, never as silent
`allow`.

## Consequences
- **Upside:** an incomplete ruleset is safe by construction. Forgetting
  to write a rule for a new action type stops that action for review
  instead of silently permitting it. This was proven concretely during
  the `listapp` build: without adding `DESTRUCTIVE_COMMAND_REQUIRES_HIL`,
  every `run_command` — including harmless ones like `ls -la` — would
  otherwise have needed HIL, or worse, would have been silently allowed
  under the old default.
- **Downside:** ruleset authors must proactively write allow rules for
  every category of routine, low-risk action a real backend needs to
  perform, or the system becomes impractically HIL-heavy (demonstrated
  directly: `listapp`'s own build needed two narrow, explicit allow
  rules — `LISTAPP_SOURCE_WRITE_ALLOWED`, `LISTAPP_BUILD_COMMANDS_ALLOWED`
  — before it was usable at all).
- **Implication for future work:** as more execution backends and action
  types are added (Git operations, other tool types), expect this same
  pattern — a new coverage gap will surface as excessive `require_hil`
  prompts before anyone gets around to writing the allow rule. That's
  the system working as designed, not a bug to route around.
