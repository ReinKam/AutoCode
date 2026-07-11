"""
canUseTool enforcement adapter.

Contract:
    SDK tool call
      -> normalize_to_action_proposal()
      -> (minimal structural validation)
      -> canonical input_hash
      -> classify_risk() [v0 stub]
      -> match_rules()
      -> resolve()
      -> emit PolicyDecision (+ AuditEvent)
      -> ALLOW | BLOCK_REQUIRE_HIL | BLOCK_DENY_UNTIL_CHANGED | BLOCK_DENY_PERMANENT

This module NEVER executes the underlying tool call. It only ever answers
the question "is this allowed", and hands back a result the Claude Agent
SDK's canUseTool callback can return directly (shape: {"behavior": "allow"
| "deny", ...}). Whatever calls this adapter is responsible for actually
running (or not running) the tool based on the verdict.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from normalize import normalize_to_action_proposal
from rule_matcher import match_rules
from precedence import Effect, resolve
from risk_classifier_stub import classify_risk
from canonical_hash import sha256_hex
from audit_log import AuditLog
from ttl_policy import compute_expires_at

POLICY_SCHEMA_VERSION = "1.0.0"

_DECISION_TO_BEHAVIOR = {
    Effect.allow: "ALLOW",
    Effect.require_hil: "BLOCK_REQUIRE_HIL",
    Effect.deny_until_changed: "BLOCK_DENY_UNTIL_CHANGED",
    Effect.deny_permanent: "BLOCK_DENY_PERMANENT",
}

_REQUIRED_ACTION_PROPOSAL_FIELDS = (
    "action_proposal_id", "action_type", "proposed_by", "paths", "created_at",
)


class InvalidActionProposalError(ValueError):
    pass


def _validate_action_proposal(proposal: dict) -> None:
    missing = [f for f in _REQUIRED_ACTION_PROPOSAL_FIELDS if f not in proposal]
    if missing:
        raise InvalidActionProposalError(
            f"ActionProposal missing required field(s): {missing}. "
            f"Refusing to evaluate an unvalidated proposal."
        )


@dataclass(frozen=True)
class AdapterResult:
    behavior: str  # ALLOW | BLOCK_REQUIRE_HIL | BLOCK_DENY_UNTIL_CHANGED | BLOCK_DENY_PERMANENT
    action_proposal: dict
    policy_decision: dict
    sdk_permission_result: dict


def _build_policy_decision(
    action_proposal: dict,
    input_hash: str,
    risk_tier: str,
    risk_classifier_version: str,
    ruleset_version: str,
    resolution,
    created_at: datetime,
    previous_decision_id: Optional[str] = None,
) -> dict:
    decision = {
        "policy_decision_id": str(uuid.uuid4()),
        "policy_schema_version": POLICY_SCHEMA_VERSION,
        "policy_ruleset_version": ruleset_version,
        "risk_classifier_version": risk_classifier_version,
        "action_proposal_id": action_proposal["action_proposal_id"],
        "input_hash": input_hash,
        "pass": "post-risk",  # MVP scope note: see README — ruleset does not yet
                                # distinguish pre-risk-only structural rules, so
                                # this adapter performs a single evaluation pass.
        "decision": resolution.decision.name,
        "risk_tier": risk_tier,
        "matched_rules": [
            {
                "rule_id": r.rule_id,
                "effect": r.effect.name,
                "approvable": r.approvable,
                "overridden": r.overridden,
            }
            for r in resolution.resolved_rules
        ],
        "reason_code": resolution.reason_code,
        "required_approvals": [],
        "hil_decision_ids": [],
        "expires_at": compute_expires_at(resolution.decision.name, created_at),
        "previous_decision_id": previous_decision_id,
        "created_at": created_at.isoformat(),
    }
    decision["decision_hash"] = sha256_hex(decision)
    return decision


def can_use_tool(
    tool_name: str,
    tool_input: dict,
    *,
    ruleset: dict,
    proposed_by: str = "claude-agent-sdk",
    hil_decisions: Optional[list] = None,
    audit_log: Optional[AuditLog] = None,
    previous_decision_id: Optional[str] = None,
) -> AdapterResult:
    proposal = normalize_to_action_proposal(tool_name, tool_input, proposed_by)
    _validate_action_proposal(proposal)

    input_hash = sha256_hex(proposal)
    risk_tier, risk_classifier_version, _signals = classify_risk(proposal)

    matched = match_rules(proposal, risk_tier, ruleset)
    resolution = resolve(
        matched_rules=matched,
        hil_decisions=hil_decisions or [],
        risk_tier=risk_tier,
        default_effect_on_no_match=Effect[ruleset["precedence"]["default_effect_on_no_match"]],
    )

    now = datetime.now(timezone.utc)
    policy_decision = _build_policy_decision(
        action_proposal=proposal,
        input_hash=input_hash,
        risk_tier=risk_tier,
        risk_classifier_version=risk_classifier_version,
        ruleset_version=ruleset["ruleset_version"],
        resolution=resolution,
        created_at=now,
        previous_decision_id=previous_decision_id,
    )

    if audit_log is not None:
        audit_log.record(
            "POLICY_DECISION_CREATED",
            policy_decision,
            correlation={
                "action_proposal_id": proposal["action_proposal_id"],
                "policy_decision_id": policy_decision["policy_decision_id"],
            },
        )

    behavior = _DECISION_TO_BEHAVIOR[resolution.decision]

    if behavior == "ALLOW":
        sdk_result = {"behavior": "allow", "updatedInput": tool_input}
    else:
        sdk_result = {
            "behavior": "deny",
            "message": (
                f"Blocked by AutoCode policy: {policy_decision['reason_code']} "
                f"(decision={behavior}, policy_decision_id={policy_decision['policy_decision_id']})"
            ),
        }

    return AdapterResult(
        behavior=behavior,
        action_proposal=proposal,
        policy_decision=policy_decision,
        sdk_permission_result=sdk_result,
    )
