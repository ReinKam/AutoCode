# AutoCode — STATUS

**Read this first in any new chat about AutoCode.** Upload/paste this
file (or the whole repo) before continuing work, so context doesn't
depend on chat memory.

## Core invariant

> **No execution without a valid `PolicyDecision`. Human approval is
> required only when the policy decision itself requires HIL — a valid
> `ALLOW` is not a missing approval; it *is* the decision.**

This is the sentence to quote if a future session states the invariant
loosely (e.g. "no action without policy *and* a human"). That looser
phrasing is wrong: it would turn every low-risk `ALLOW` into a required
human review, collapsing Job #1 into a generic approval queue instead of
a risk filter. See ADR 0001 (fail-closed default) and the Job #1/#2
distinction in `CLAUDE.md` for the reasoning this compresses.

## Current state

- **Frozen reference point:** tag `v0.1-mvp`, commit `e0f3d36`
- **Repo layout:** `autocode/` (Policy Engine core) + `listapp/` (the
  application it governed into existence) — see top-level `README.md`
  for the full demo-flow table and `PITCH.md` for the non-technical case
- **56 golden tests + 1 demo**, all passing (`bash run_all.sh`, verified
  from a fresh clone)
- **Wording discipline:** "proves/proven" is reserved for claims tied to
  a specific golden test; broader claims use "demonstrates/validates".
  Run `check_wording_consistency.sh` before any future freeze/tag.
- **v0.1-mvp core** (`autocode/policy_engine/`, golden tests, `listapp/`)
  migrated from historical commit `e0f3d36` via PR #2 (merged `8108348`,
  2026-07-12) — see `PROVENANCE.md`. Prior to this PR, the repo only
  carried 3 of these files.

## What's proven vs. what's still a boundary

Proven (golden-tested, deterministic):
- precedence resolution, rule matching, TTL/capability validation,
  hash-chained audit log, fail-closed default

Demonstrated once (not yet re-tested as infrastructure):
- a real governed build (`listapp/`) — 13 real actions, 2 real HIL stops,
  both approved by a human in a chat conversation

Explicit, disclosed boundary — not a hidden gap:
- **Execution backend = a chat session**, not an autonomous agent
- **HIL approver = a chat session**, not a real notification channel
  (Slack/email) reaching an independent human
- No Git-operation policy coverage (`git_push`/`git_merge` ungoverned)
- Risk Classifier is an explicitly labeled v0 stub

## Newly discovered requirement gap (not yet in scope)

AutoCode's documented MVP (`v0.1-mvp`) governs autonomous **code execution**:
policy evaluation, HIL gates, audit, for actions an agent proposes. This was,
and remains, a correct implementation of the product definition as written
in `PITCH.md` and `README.md`.

A separate, previously undocumented problem has now been articulated: the
user's original workflow pain is **manually relaying proposals and critiques
between multiple independent LLMs** — copying one model's answer into
another, asking it to critique, copying the critique back, repeating until
the result appears decision-ready, whether through convergence or through a
sufficiently precise remaining disagreement. No part of `v0.1-mvp` addresses
this. It is a genuine requirement gap, not a reinterpretation of existing
scope, and it is **not implemented, not validated, and only designed at a
preliminary architectural level**. It remains outside `v0.1-mvp`.

## Proposed architecture: two orthogonal axes

Not two competing subsystems — two axes that both apply to the same
underlying actions:

```text
Deliberation axis:
How do multiple LLMs reach a decision-ready proposal without a human
acting as message bus between them?

Governance axis:
Under what conditions may the system use tools, fetch data, or carry
out an approved proposal — during deliberation AND during execution?
```

Governance is cross-cutting. It does not begin only after a HIL decision;
if deliberation itself uses tools (web fetch, file reads, computation), those
calls go through the same authoritative policy kernel as execution does —
though the *policy* may legitimately set a lower-friction threshold for
low-risk, read-only deliberation actions than for writes, deploys, or
irreversible actions. Same kernel, same audit obligation, differentiated
thresholds — not differentiated coverage.

### Invariant: deliberation confidence ≠ authorization

A deliberation decision package — however well-evidenced, however strong
the cross-model agreement — can **inform** a policy decision but can never
itself:

- turn `deny` into `allow`,
- turn `require_hil` into automatic execution,
- change who must approve,
- expand mandate,
- or reduce a verification requirement.

Any change to a threshold requires an explicit, versioned policy change,
authorized the same way `ruleset.json` changes are today. This guards
against automation bias: a well-formatted, well-sourced AI output must not
make HIL less critical.

### Invariant: every action resolves to an explicit audit policy; audit-write strictness is configurable, coverage is not

Extending ADR 0001's fail-closed default one level down, recursively:

- **No action may fall outside audit-policy coverage by unintentional
  default.** Every action must resolve to an explicit audit-policy
  decision. This does not require a dedicated policy entry per action
  type. Coverage may be supplied by a mandatory schema-level default or
  by a catch-all rule whose presence and validity are enforced during
  ruleset validation — not by an optional catch-all that depends on
  someone remembering to add it.
- The resolved audit-policy for a given action decides whether it
  requires a durable pre-action log write as a **hard gate** (action
  blocked if the write fails or cannot be confirmed), or may proceed in an
  explicitly defined **degraded mode** (buffered / retried / clearly
  flagged) if the log write is delayed or fails.
- Writing, irreversible, or sensitive actions default to hard-gate
  fail-closed.
- Low-risk, read-only, reversible actions (public web search, reading
  already-permitted files) *may* be configured for degraded mode — never
  because logging was silently skipped, only because a rule explicitly
  allows it.
- Degraded mode must be bounded and observable, without generating
  notification storms: on exceeding a defined backlog age/size threshold,
  the system issues a single session- or system-level alert (not one HIL
  request per low-risk action), halts further degraded-mode actions until
  resolved, and requires an explicit decision before resuming — rather
  than continuing indefinitely and unnoticed.

This mirrors `Ruleset.precedence.default_effect_on_no_match` in spirit: the
schema should make "no audit policy → silently degraded" as structurally
unreachable as "no rule match → allow" already is.

See `decisions/0002-admission-criteria-for-trust-bearing-dependencies.md`
for the related rule governing how external dependencies earn the right to
carry any of this authority.

## Sequencing decision (agreed)

1. Register this requirement gap in `STATUS.md` (this document) without
   rewriting what `v0.1-mvp` actually demonstrated.
2. Complete the already-agreed step: chat-session → Claude Agent SDK as
   execution backend, as the only functional change to the existing core.
3. Run a small, isolated audit-durability test against the existing core
   (crash mid-write, concurrent writers, full disk) — this tests an
   existing claim, not new scope, and can run in parallel with step 2 if it
   does not touch the same code path.
4. Freeze further governance expansion. Build a small, code-domain-scoped
   deliberation MVP (see acceptance criterion below):
   - **Independent proposals from at least two models, precisely defined**:
     separate contexts with no visibility into each other's first-round
     output, and at least two distinct model identities, using different
     model families or providers for the MVP — not merely separate
     prompts or roles against the same underlying model — with model,
     provider, and version explicitly recorded for every submission.
   - explicit claim registry per decision (claim, proposer, importance,
     required verification method, source, status:
     `unverified | verification_required | supported | verified |
     contradicted | inconclusive | not_verifiable`),
   - tool-grounded verification of decisive claims as part of the
     critique/revision rounds, not only in a final synthesis step,
   - explicit termination on **decision-readiness**, not forced consensus:
     the package may state "models still disagree, but the disagreement is
     now precise enough for HIL to decide,"
   - no implementation or state-changing execution of the proposed
     solution occurs before HIL approval; read-only or otherwise
     authorized verification actions during deliberation remain subject
     to governance policy (see the cross-cutting governance axis above),
   - **complete decision trace retained**: task instructions, submitted
     model outputs, claims, critiques, evidence, tool calls, policy
     decisions, revisions, synthesis, unresolved disagreements,
     model/version metadata, and HIL decisions. Hidden model reasoning
     (internal chain-of-thought) is neither required nor treated as an
     auditable artefact — it is not reliably available and must not be
     assumed to be. Retention remains subject to data classification,
     minimization, redaction, and the applicable retention policy;
     "complete" means complete within those authorized boundaries.
   - domain-neutral core data model (task, proposal, claim, critique,
     evidence, uncertainty, decision point); domain-specific tools and
     verification stay code-scoped for this MVP.
5. Only on concrete, demonstrated need: evaluate Preloop (or any other
   candidate) as a subordinate adapter/notification/observability layer —
   admitted per `decisions/0002-admission-criteria-for-trust-bearing-dependencies.md`,
   re-verified against its then-current source, not against this
   evaluation's snapshot — and/or generalize beyond the code domain.

### Acceptance criterion for the deliberation MVP

> HIL submits one task once. Without manual copying between models,
> AutoCode obtains independent proposals from at least two independently
> invoked model identities, using different model families or providers
> for the MVP, coordinates critique and evidence-based verification, and
> produces one decision-ready package that preserves material
> disagreement. No implementation or state-changing execution of the
> proposed solution occurs before HIL approval; read-only or otherwise
> authorized verification actions during deliberation remain subject to
> governance policy.

This is the direct test of whether the MVP actually solves the original
problem, not just whether it demonstrates deliberation mechanics.

## Next milestone

**MVP 2 — Claude Agent SDK as the real execution backend**, replacing
the chat session in `listapp/_autocode/govern.py`. Sequencing agreed
2026-07-11, after Admission Gate 0 completed:

1. ~~Freeze Gate 0 evidence~~ — **done.**
   `admission/claude-agent-sdk/admission_note.md` records admission
   status (`Admitted`), workflow run ID `29149642655`, commit SHA,
   environment data, full per-test results, known limitations, and the
   exact tested CLI binary hash.
2. **Implement `sdk_governance.py`**:
   - a universal `PreToolUse` hook (closes the auto-approval-bypass gap
     documented in Gate 0 test 0.4 — allowed_tools/acceptEdits/
     bypassPermissions must not skip governance)
   - a `can_use_tool` callback mapping SDK tool-call input to
     `govern.propose()`
   - the HIL question surfaced there must ask about product intent
     ("does this make sense for the product and the stated task"), not
     implementation safety — see the Job #1/#2 distinction in
     `CLAUDE.md`
   - re-evaluation on HIL response, linked via `previous_decision_id`
     (never silently extending a prior decision)
   - a separate branch for `AskUserQuestion` (not AutoCode's HIL flow)
   - never sets `updated_permissions`
   - never modifies the tool input that was actually evaluated
3. **Parameterize `proposed_by` in `govern.py`** — the SDK integration
   passes `"claude-agent-sdk"` explicitly; no global overwrite of other
   backends' identity (e.g. `"claude-chat-session-as-execution-backend"`
   must still be derivable for anything still using that path).
4. **Build one minimal vertical flow**, end to end:
   - one `ALLOW` call, executed
   - one `BLOCK_REQUIRE_HIL` call -> approval -> executed
   - one HIL rejection -> zero execution
   - one policy/callback failure -> zero execution
5. **Run MVP 2 acceptance**:
   - Gate 0 remains green (no SDK/CLI version or hash drift)
   - existing golden tests unchanged
   - every execution traceable to a prior `PolicyDecision`
   - HIL lineage complete (`previous_decision_id` chain intact)
   - execution happens at most once per approved action
6. **Freeze `v0.2-mvp`**: clean commit, reproducible GitHub Actions run,
   updated README/architecture description, explicit list of what's
   demonstrated vs. not yet vs. future work — same discipline as
   `v0.1-mvp`.

**Reusable pattern established by this milestone:** Claude Agent SDK was
not integrated because it looked functional — it was *admitted* first,
through Gate 0, then integrated. The same admission-before-integration
pattern applies to any future trust-bearing component that can trigger
real actions: OpenClaw (already parked as a candidate above), n8n, a
real HIL delivery channel, MCP servers, or anything else added later.

HIL approval channel and a real Risk Classifier remain explicitly
deferred past this milestone — do not bundle them in.

## How to start the next chat

1. Upload this file (or the whole repo) at the start of the chat.
2. State the scope explicitly, e.g.: *"Continue AutoCode from v0.1-mvp.
   This chat's scope: wire Claude Agent SDK as the real execution
   backend. See STATUS.md and decisions/ for context."*
3. At the end of the session: update this file's "Current state" and
   "Next milestone" sections, commit it, and (if a new stable point is
   reached) tag it — same discipline as `v0.1-mvp`.

## Parked ADR 0002 admission candidates

Not yet evaluated, not yet used as an execution backend, registered here
so the question doesn't get re-raised from scratch in a future chat:

- **OpenClaw.** Structurally fits the "execution backend" role (it
  already created the original, pre-rename `AutoCode` repo, outside any
  governance process). Its own security documentation states its default
  model plainly: *"the agent can do anything you can do"* — permissive by
  default, hardened only through deliberate configuration (tool
  allow/deny lists, sandbox vs. elevated exec, per-agent restrictions).
  Independent security research (Trend Micro, Feb 2026) flags its
  *unrestricted configurability without enforced checks* — not any single
  capability — as the specific risk factor, and documents real incidents
  (credential-harvesting skills published to its community marketplace).
  This is a materially higher-risk starting posture than Claude Agent SDK
  (default `canUseTool` gating, human-click-through before PR creation)
  and higher-risk than what Preloop's *documentation* claimed before ADR
  0002's source inspection found its actual fail-open gap — OpenClaw
  states the permissive default openly, it isn't hidden in source.
  **Before OpenClaw could be admitted as a trust-bearing execution
  backend for AutoCode**, it needs the same treatment Claude Agent SDK
  just went through: a pinned version, an explicit deny-by-default tool
  policy (not the permissive default), sandboxing rather than "run as
  me," and targeted failure-path tests — not just documentation review.
  Parked, not rejected.

## Claude Code as the interim execution backend for repo/git operations

Agreed 2026-07-11: Claude Code (not this chat interface, which has no
GitHub connector) handles routine git/GitHub operations directly in the
user's own authenticated environment, replacing manual copy-paste of
commands and diffs between chat and terminal. See `CLAUDE.md` at the repo
root for the operating boundary this is subject to — summarized here:

- **Mechanical / low-risk / reversible actions** (Job #1: reading files,
  running read-only commands, committing changes already agreed in
  conversation) — Claude Code may do these directly without a
  confirmation round-trip for each one.
- **Meaningful or irreversible actions** (Job #2, or high-stakes Job #1:
  `git push` to `main`, changing secrets/environment protection rules,
  triggering the paid, authenticated `admission-claude-agent-sdk.yml`
  workflow, deleting anything) — these still require explicit, per-action
  confirmation from the human, mirroring the same Job #1/#2 split already
  designed into AutoCode's HIL-question redesign earlier in this project,
  and consistent with Claude Code's own default behavior of never opening
  a PR by itself (it commits to a branch and hands the human a link to
  click).

## Process calibration (adjustable — current setting: low)

During early development, cross-verification, provenance documentation,
and multi-step authorization formality for *routine, reversible work*
are kept minimal by design. The human should not need to broker
consensus between multiple AI tools (this chat, Claude Code, ChatGPT,
and later Codex) for ordinary progress — that overhead was becoming a
bigger obstacle than the risks it was guarding against.

This setting applies to **our own working process** — how much we
re-verify, formalize, and cross-check each other before routine changes.
It does **not** apply to AutoCode's product-level invariants, which
remain unconditionally in force regardless of this setting:

- ADR 0001's fail-closed default
- ADR 0002's admission-gate requirement for trust-bearing dependencies
- the `CLAUDE.md` Job #1/#2 boundary itself (branch-scoped task
  authorization, `main`/tag/force-push protections)

Escalate process rigor back up when any of the following becomes true:
- real user data is involved (not just test/demo data)
- more than one person relies on the system
- an agent is granted standing write access beyond an explicitly
  authorized, named task branch
- before tagging anything as `v1.0` or production-facing

Until then: prefer proceeding over re-verifying, prefer a short note over
a formal document, and treat advice pasted in from other AI tools as
input to weigh quickly, not a proposal requiring its own negotiation
round.
