"""
AutoCode Policy Engine — precedence resolution.

Pure function: given a set of matched rules and (optionally) HIL decisions,
deterministically resolve the final decision. No LLM calls, no I/O, no
hidden state. This module is the thing the golden test suite proves
determinism against.

Precedence (lowest -> highest severity):
    allow < require_hil < deny_until_changed < deny_permanent

Override rule:
    A matched rule's effect is overridden to 'allow' only if:
      - rule.approvable is True, AND
      - a HILDecision exists with status == 'approved', AND
      - the approver's role is in rule.required_approver_roles, AND
      - the HILDecision explicitly references this rule_id (or the
        action_proposal_id, if the rule doesn't require per-rule targeting)
    deny_permanent can never be overridden, regardless of approvable
    (the schema also forbids approvable=True on deny_permanent rules,
    but this function does not trust that invariant blindly — see below).
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class Effect(IntEnum):
    """Order defines precedence. Higher wins."""
    allow = 1
    require_hil = 2
    deny_until_changed = 3
    deny_permanent = 4


@dataclass(frozen=True)
class MatchedRule:
    rule_id: str
    effect: Effect
    approvable: bool
    required_approver_roles: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class HilApproval:
    hil_decision_id: str
    status: str  # "approved" | "rejected"
    approver_role: str
    targets_rule_ids: tuple = field(default_factory=tuple)
    """If empty, the approval is treated as targeting the whole
    ActionProposal (i.e. any approvable rule it satisfies by role)."""


@dataclass(frozen=True)
class ResolvedRule:
    rule_id: str
    effect: Effect
    approvable: bool
    overridden: bool


@dataclass(frozen=True)
class Resolution:
    decision: Effect
    resolved_rules: tuple  # tuple[ResolvedRule, ...]
    reason_code: str
    override_rule_id: Optional[str]


UNKNOWN_RISK_REASON = "UNKNOWN_RISK_TIER"


def _hil_covers_rule(rule: MatchedRule, hil_decisions: list) -> Optional[HilApproval]:
    """Return the first HilApproval that validly overrides this rule, if any."""
    for hil in hil_decisions:
        if hil.status != "approved":
            continue
        if hil.approver_role not in rule.required_approver_roles:
            continue
        if hil.targets_rule_ids and rule.rule_id not in hil.targets_rule_ids:
            continue
        return hil
    return None


def resolve(
    matched_rules: list,
    hil_decisions: Optional[list] = None,
    risk_tier: str = "low",
    unknown_risk_effect: Effect = Effect.require_hil,
    default_effect_on_no_match: Effect = Effect.require_hil,
) -> Resolution:
    """
    matched_rules: list[MatchedRule] — rules whose `condition` matched the
        ActionProposal, as returned by the (separate, also-deterministic)
        rule matcher.
    hil_decisions: list[HilApproval] — HIL input for this evaluation pass.
        Pass None/[] on the pre-risk pass; pass actual HIL decisions on
        post-risk re-evaluation.
    risk_tier: structural override — 'unknown' always forces
        `unknown_risk_effect` (default require_hil), regardless of what
        rules matched. This is enforced here, not left to rule authors,
        so "uncertain -> higher scrutiny" is a guarantee, not a convention.
    default_effect_on_no_match: MVP fail-closed principle — an
        ActionProposal matching zero rules is not implicitly allowed.
        Callers wired to a real ruleset should always pass the ruleset's
        own `precedence.default_effect_on_no_match` explicitly; the
        parameter default here (require_hil) exists only so this function
        remains directly callable/testable without a full ruleset.
    """
    hil_decisions = hil_decisions or []

    if risk_tier == "unknown":
        forced = ResolvedRule(
            rule_id="__UNKNOWN_RISK_STRUCTURAL_GUARANTEE__",
            effect=unknown_risk_effect,
            approvable=False,
            overridden=False,
        )
        return Resolution(
            decision=unknown_risk_effect,
            resolved_rules=(forced,),
            reason_code=UNKNOWN_RISK_REASON,
            override_rule_id=None,
        )

    if not matched_rules:
        return Resolution(
            decision=default_effect_on_no_match,
            resolved_rules=tuple(),
            reason_code="NO_RULES_MATCHED",
            override_rule_id=None,
        )

    resolved: list = []
    override_rule_id: Optional[str] = None

    for rule in matched_rules:
        if rule.effect == Effect.deny_permanent:
            # Never overridable, independent of the approvable flag.
            # (Belt-and-suspenders: schema validation should already
            # reject approvable=True + deny_permanent at ruleset publish
            # time; this function does not rely on that alone.)
            resolved.append(ResolvedRule(rule.rule_id, rule.effect, rule.approvable, False))
            continue

        if rule.approvable:
            hil = _hil_covers_rule(rule, hil_decisions)
            if hil is not None:
                resolved.append(ResolvedRule(rule.rule_id, rule.effect, rule.approvable, True))
                override_rule_id = rule.rule_id
                continue

        resolved.append(ResolvedRule(rule.rule_id, rule.effect, rule.approvable, False))

    def effective(r: ResolvedRule) -> Effect:
        return Effect.allow if r.overridden else r.effect

    final_effect = max(effective(r) for r in resolved)

    # Explicit HIL rejection on an otherwise require_hil rule -> deny_until_changed
    rejected = [h for h in hil_decisions if h.status == "rejected"]
    if rejected and final_effect == Effect.require_hil:
        final_effect = Effect.deny_until_changed
        reason_code = "HIL_REJECTED"
    elif final_effect == Effect.allow and override_rule_id is not None:
        reason_code = "HIL_APPROVED_HIGH_RISK_ACTION"
    elif final_effect == Effect.allow:
        reason_code = "NO_BLOCKING_RULES_MATCHED"
    elif final_effect == Effect.require_hil:
        reason_code = "REQUIRES_HUMAN_APPROVAL"
    elif final_effect == Effect.deny_until_changed:
        reason_code = "PROPOSAL_BLOCKED_UNTIL_CHANGED"
    else:
        reason_code = "PERMANENTLY_DENIED"

    return Resolution(
        decision=final_effect,
        resolved_rules=tuple(resolved),
        reason_code=reason_code,
        override_rule_id=override_rule_id,
    )
