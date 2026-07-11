# ADR 0002 — Admission criteria for trust-bearing external dependencies

## Status
Accepted

## Context

During the evaluation of Preloop as a candidate governance/adapter layer,
its published README and `ARCHITECTURE.md` described policy-as-code,
fail-closed evaluation-error handling, and a "Full Audit Trail." Direct
inspection of `policy_evaluator.py`, `dynamic_fastmcp.py`, and
`approval_helper.py` at a pinned ref showed the opposite for the load-bearing
case ADR 0001 exists to prevent: unmatched rules, missing tool
configuration, and — critically — exceptions raised by the policy
evaluation call itself all resolve to `allow`, with explicit developer
comments reading "Fail open for evaluation errors to avoid blocking all
tools" and "Fail-open: if approval check fails, allow execution." None of
this was visible from documentation alone; it only became visible by
reading the actual execution and exception-handling paths.

The same pattern recurred, at smaller scale, while surveying candidates for
the multi-model deliberation MVP:

- n8n's Microsoft Teams "Send and Wait for Response" node — a candidate HIL
  mechanism — has multiple independently reported, reproducible cases
  (`n8n-io/n8n#25311`, across versions 2.4.6–2.11.1, multiple platforms and
  databases) of resuming a paused workflow toward either the approved or
  declined branch **without any user interaction**. Documentation describes
  the pause/resume mechanism; it establishes no invariant about what
  happens when resumption is triggered incorrectly.
- Open Model Council's fusion-judge synthesis step silently falls back to a
  generic, unstructured report when the judge model's output fails to
  parse, and continues to synthesis regardless — again, only visible in
  `route.ts`, not in the project's description of itself.

In every case, the gap was between what the component was *described* as
doing and what its own execution and failure paths actually did.
Documentation, README claims, and even architecture docs are written by the
same team that wrote the code and share its blind spots; they are not an
independent check.

This is expensive to catch after the fact and cheap to catch before
adoption. It should be a standing admission gate, not a one-off audit
performed only when a disagreement forces it.

## Decision

A dependency is **trust-bearing** if it can affect security, authorization,
HIL approval, evidence/claim status, decision integrity, or audit —
i.e., anything ADR 0001's fail-closed invariant or the deliberation
layer's claim-registry and decision-trace guarantees depend on.

Trust-bearing status is determined by how AutoCode uses the dependency,
not by the dependency's general category. A normally ordinary helper
library becomes trust-bearing if its output or failure mode can affect
authorization, evidence status, audit integrity, or whether an action
proceeds — a JSON parser reading `ruleset.json`, or an HTTP client handling
approval-webhook responses, is trust-bearing regardless of how generic it
looks on a dependency list. Libraries whose failure mode has no bearing on
any of these — formatting, logging cosmetics, unrelated UI concerns — do
not require this process; applying it to them would be needless friction
without a corresponding safety benefit.

Before a trust-bearing external dependency is allowed to carry authority
in any environment, and before it is relied upon in production, the
admission record must include:

1. **Locked version and commit SHA.** The dependency is evaluated as a
   specific, pinned reference, not "the project" in the abstract. Findings
   do not carry forward across upgrades without re-verification. For
   packaged or deployed software, the admission record must also identify
   the exact runtime artefact by immutable digest or checksum and
   establish its relationship to the inspected source reference — a
   container digest, package checksum, build/release identity, or SBOM, as
   applicable. A commit SHA proves what was read; it does not by itself
   prove what is running.
2. **Identification of the relevant execution and failure paths** — which
   code paths actually run when the dependency is invoked in AutoCode's
   use case, and which paths run when something goes wrong (exceptions,
   timeouts, unavailable upstream services, malformed input).
3. **Direct source code inspection of those paths**, specifically wherever
   the dependency carries authority (i.e., its output or failure mode
   determines whether an action proceeds). Documentation, README files, and
   marketing pages may inform where to look and may be supporting evidence
   of published interfaces or vendor commitments, but are never sufficient
   evidence of authoritative runtime or failure-path behaviour.
4. **Targeted failure tests** exercising the identified failure paths
   (forced exceptions, unavailable dependencies, malformed responses,
   timeouts, restarts mid-operation) — not just the happy path.
5. **Explicit fail-open/fail-closed classification** of each identified
   failure path, stated plainly enough to be checked against ADR 0001's
   invariant for any path that gates execution.
6. **A record of what is verified, what is demonstrated, and what remains
   unknown** — the same `proven` vs. `demonstrated` discipline already in
   force for AutoCode's own code applies to adopted dependencies.
7. **Re-assessment on upgrade.** Any upgrade invalidates the assumption
   that the prior admission applies unchanged. A diff- and risk-based
   review determines whether targeted re-verification is sufficient or
   full re-admission is required. Changes to relevant execution,
   authority, persistence, approval, or failure paths always require
   re-testing, regardless of how the upgrade is otherwise described.
   Material changes to configuration, deployment topology, enabled
   integrations, policy defaults, or authority boundaries are treated like
   upgrades and require risk-based re-verification — the Preloop finding
   demonstrated that security semantics may depend on defaults and
   configuration as well as versioned code, and admission must cover all
   three.
8. **External documentation alone is never sufficient evidence** for
   admission, regardless of how detailed, confident, or professionally
   presented it is.

### When the relevant paths cannot be inspected

Some vendors do not expose the implementation behind a trust-bearing
component — closed-source software, opaque hosted SaaS, or a service whose
internals are contractually shielded. This does not exempt the component
from this decision; it changes what admission can mean:

> If the relevant authoritative execution and failure paths cannot be
> inspected, the dependency must not become the sole authority for
> security, approval, evidence status, or execution. It may only be used
> in a subordinate role behind an independently enforced AutoCode control.

Concretely, one of three outcomes applies:

- The component cannot hold an authoritative role at all.
- It is isolated behind AutoCode's own fail-closed core, used only for
  functions AutoCode does not depend on for correctness — e.g., a
  notification or UX surface whose output AutoCode's own policy kernel
  independently verifies before acting, never the source of truth for
  whether an action is permitted.
- It is accepted into a subordinate role only with compensating evidence:
  contractual guarantees plus AutoCode's own runtime fault-injection
  testing of the integration boundary, since the vendor's internal
  behaviour cannot be read directly and must instead be characterized from
  the outside.

## Consequences

**Upside:** trust-bearing dependencies are evaluated against what they
actually do, not what they claim to do, before AutoCode's invariants come
to depend on them. This would have caught Preloop's fail-open evaluation
path, and the n8n Teams node's unreliable resume behavior, before either
was wired into a production decision path rather than after.

**Downside:** this adds real friction and time cost to adopting any
component in the trust-bearing category — source reading and targeted
failure testing take longer than reading a README. It should not be
applied reflexively to every dependency; the scope boundary in this
decision (trust-bearing vs. ordinary) exists specifically to keep that
cost proportionate.

**Implication for future work:** expect this process to occasionally
disqualify components that look complete and well-documented on the
surface — that is the process working as intended, not friction to route
around. When it does, the disqualification applies to the pinned version
inspected, not to the project indefinitely; a later version may pass.
