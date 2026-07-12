# AutoCode — Policy Engine MVP

A deterministic, policy-first control plane for autonomous software
development. This MVP is built around one core claim, verified by golden
tests: **no execution backend acts on an ActionProposal without a valid,
unexpired, hash-verified PolicyDecision** — and that decision is produced
by a pure, fully tested, deterministic evaluation, not by an LLM's
judgment call.

This is a policy **core**, not a full AutoCode system. It answers one
question — *"is this specific action allowed right now?"* — correctly,
deterministically, and auditable. Everything else (a real Risk
Classifier, Git integration, multiple execution backends, a HIL
notification UI) is explicitly out of scope for this MVP. See
[Scope](#scope) below.

## Architecture

```
SDK tool call (e.g. Claude Agent SDK canUseTool)
    │
    ▼
normalize_to_action_proposal()        [normalize.py]
    │  strict, explicit tool_name -> action_type mapping; no guessing
    ▼
ActionProposal                        [schemas/action_proposal.schema.json]
    │
    ▼
classify_risk()  [v0 STUB]            [risk_classifier_stub.py]
    │  deterministic placeholder — NOT the final Risk Classifier design
    ▼
RiskAssessment                        [schemas/risk_assessment.schema.json]
    │
    ▼
match_rules()                         [rule_matcher.py]
    │  pure function: ActionProposal + risk_tier + Ruleset -> matched_rules[]
    │  AND across condition fields present on a rule, ANY within a field
    ▼
resolve()                             [precedence.py]
    │  pure function: precedence + approvable/HIL override logic
    │  deny_permanent > deny_until_changed > require_hil > allow
    │  unknown risk_tier and "no rules matched" both fail CLOSED (require_hil)
    ▼
PolicyDecision                        [schemas/policy_decision.schema.json]
    │  a time-boxed capability ticket (see ttl_policy.py, capability.py)
    │  decision_hash + input_hash make it tamper-evident and re-verifiable
    ▼
AuditEvent (hash-chained)             [schemas/audit_event.schema.json, audit_log.py]
    │
    ▼
ALLOW | BLOCK_REQUIRE_HIL | BLOCK_DENY_UNTIL_CHANGED | BLOCK_DENY_PERMANENT
    │
    ▼
can_use_tool_adapter.py returns this verdict to the SDK's canUseTool
callback. It NEVER executes the tool call itself.
```

### Key invariants verified by golden tests (not just documented)

- **Capability-based execution.** A `PolicyDecision` only permits action
  if `decision == "allow"`, it hasn't expired, and its `input_hash`
  still matches the exact `ActionProposal` being acted on
  (`capability.py::validate_capability`).
- **Re-evaluate, never extend.** A HIL approval never extends an
  existing `PolicyDecision`'s expiry — it is only ever an input to a
  brand-new evaluation, which gets its own fresh TTL
  (`tests/golden_test_suite_ttl.py`, scenario 9).
- **`deny_permanent` is never overridable**, by any role, under any
  circumstance — enforced independently in both the schema
  (`approvable` must be `false`) and in `resolve()` itself.
- **Fail-closed by default.** An `ActionProposal` matching zero rules
  is `require_hil`, not `allow`. Only an explicit `allow` rule (e.g.
  `READ_ONLY_ACTIONS_ALLOWED`) permits an action by default.
- **Unknown risk always escalates.** `risk_tier == "unknown"` forces
  `require_hil` structurally, before any rule is even evaluated.
- **Tamper-evident audit trail.** Every `AuditEvent` chains to the
  previous one's hash; mutating any past event breaks
  `AuditLog.verify_chain()` for everything after it.
- **Wrong approver role cannot override a rule**, even with an
  otherwise-valid HIL approval.

## Directory layout

```
schemas/          JSON Schema contracts (ActionProposal, RiskAssessment,
                   Ruleset, PolicyDecision, AuditEvent)
policy_engine/     The pure-function core + the canUseTool adapter
  canonical_hash.py       deterministic JSON hashing (input_hash, decision_hash, event_hash)
  rule_matcher.py         ActionProposal + risk_tier + Ruleset -> matched_rules[]
  precedence.py           matched_rules + HIL -> Resolution (the precedence algorithm)
  risk_classifier_stub.py v0 STUB — placeholder, not the final classifier
  ttl_policy.py           decision type -> concrete expires_at
  capability.py           redeem-time validation of a PolicyDecision
  audit_log.py            hash-chained, tamper-evident event log
  normalize.py            SDK tool call -> ActionProposal (4 tool types only)
  can_use_tool_adapter.py the thin enforcement adapter itself
  reference_ruleset.json  the ruleset used by all tests and the demo
tests/             One golden-test suite per layer (43 + 12 = 55 cases,
                   run individually or via run_all.sh)
demo/demo.py       The 6-scenario end-to-end walkthrough
run_all.sh         Runs every test suite + the demo, in order
```

## Running it

```bash
cd autocode
bash run_all.sh
```

Or run any piece independently:

```bash
python3 tests/golden_test_suite.py          # precedence engine only
python3 tests/golden_test_suite_matcher.py  # rule matcher only
python3 tests/golden_test_suite_adapter.py  # canUseTool adapter only
python3 tests/golden_test_suite_ttl.py      # TTL + capability validation
python3 demo/demo.py                        # the 6-scenario walkthrough
```

No dependencies beyond the Python 3 standard library.

## Demo flow

`demo/demo.py` walks through exactly these 6 scenarios against the real
engine (not mocked):

1. **Read a file** → `ALLOW` (matches the explicit `READ_ONLY_ACTIONS_ALLOWED` rule)
2. **Write to `/auth/**`** → `BLOCK_REQUIRE_HIL` (matches `AUTH_CHANGES_REQUIRE_HIL`, no approval yet)
3. **Same write, with a valid `security_reviewer` HIL approval** → `ALLOW`, issued as a **new** `PolicyDecision` with its own fresh TTL — not an extension of #2
4. **Delete the audit log** → `BLOCK_DENY_PERMANENT`, and this cannot be overridden by any HIL approval, ever
5. **Run `ls -la`** → `BLOCK_REQUIRE_HIL` — the fail-closed MVP default: no rule explicitly permits `run_command`, so even a harmless command stops for review
6. **An expired `ALLOW` ticket** → `capability.validate_capability()` correctly rejects it 6 minutes later (TTL was 5 minutes), even though the original decision was `allow`

## Scope

**In scope for this MVP:**
- 4 tool/action types: `file_read`, `file_write`, `file_delete`, `run_command`
- Deterministic Policy Engine (rule matcher + precedence resolution)
- Placeholder (v0 stub) Risk Classifier
- HIL as structured test input (`HilApproval`) — no real notification channel
- Hash-chained Audit Log
- TTL-based capability validation
- Golden test suites verifying determinism at every layer

**Explicitly out of scope (MVP+1 and beyond):**
- Git operations (`git_push`, `git_merge`, branch/protected-branch policy) —
  deliberately deferred: higher-consequence, needs its own condition
  fields and its own golden tests, not bolted onto this adapter
- A real Risk Classifier (the current one is a labeled stub)
- Real HIL delivery (Slack/email/Telegram gateway)
- Real Execution Backend wiring (Claude Agent SDK / Hermes / OpenClaw as
  live adapters — this MVP defines and tests the contract they'd be wired to)
- Persistent/durable storage for the Audit Log (currently in-memory)
- A "coverage engine" that reasons about which action types lack rules
  (the fail-closed default in `precedence.default_effect_on_no_match`
  handles this narrowly for now)

## Ruleset versioning

`policy_engine/reference_ruleset.json` is versioned
(`ruleset_version: "0.3.4"`) and validated against
`schemas/ruleset.schema.json` (`ruleset_schema_version: "1.1.0"`). Once a
`ruleset_version` has been referenced by any real `PolicyDecision`, its
rule content is treated as immutable — changes are shipped as a new
version, never a mutation in place. This ruleset already carries one
real example of that discipline in its own history: `DELETE_AUDIT_LOG`
and `DESTRUCTIVE_COMMAND_REQUIRES_HIL` were both added mid-development
as coverage gaps were found, each as an explicit version bump.
