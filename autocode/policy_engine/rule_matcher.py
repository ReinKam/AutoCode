"""
AutoCode Policy Engine — rule matcher.

Bridges ActionProposal + RiskAssessment + Ruleset -> matched_rules[],
which precedence.resolve() then consumes.

Pure function. No LLM calls, no I/O, no network, no filesystem access
(glob matching here is string-pattern matching against `paths` already
present in the ActionProposal — it never touches the real filesystem).

Semantics (locked per architecture discussion):
    A rule matches only if ALL condition fields that are PRESENT on the
    rule match. Omitted fields are unrestricted (not "match anything" in
    the OR sense — they simply impose no constraint).
    Within a single field, matching is OR across the field's values
    (e.g. any one of `action_types` matching is enough for that field).
    For `paths`, a rule matches if ANY path on the proposal matches ANY
    pattern in `path_matches` (a proposal touching one file under
    /auth/** is enough to trigger an /auth/** rule, even if it also
    touches unrelated files).
"""

import fnmatch
from typing import Optional

from precedence import Effect, MatchedRule


def _matches_action_type(condition: dict, action_type: str) -> bool:
    allowed = condition.get("action_types")
    if allowed is None:
        return True
    return action_type in allowed


def _matches_paths(condition: dict, paths: list) -> bool:
    patterns = condition.get("path_matches")
    if patterns is None:
        return True
    if not paths:
        # Rule requires a path constraint but proposal has no paths at all.
        return False
    return any(
        fnmatch.fnmatch(path, pattern)
        for path in paths
        for pattern in patterns
    )


def _matches_branch(condition: dict, target_branch: Optional[str]) -> bool:
    patterns = condition.get("target_branches")
    if patterns is None:
        return True
    if target_branch is None:
        return False
    return any(fnmatch.fnmatch(target_branch, pattern) for pattern in patterns)


def _matches_risk_tier(condition: dict, risk_tier: str) -> bool:
    allowed = condition.get("risk_tiers")
    if allowed is None:
        return True
    return risk_tier in allowed


def _rule_condition_matches(condition: dict, action_proposal: dict, risk_tier: str) -> bool:
    return (
        _matches_action_type(condition, action_proposal.get("action_type"))
        and _matches_paths(condition, action_proposal.get("paths", []))
        and _matches_branch(condition, action_proposal.get("target_branch"))
        and _matches_risk_tier(condition, risk_tier)
    )


def match_rules(action_proposal: dict, risk_tier: str, ruleset: dict) -> list:
    """
    Returns list[MatchedRule], preserving ruleset rule order (deterministic
    iteration order; precedence.resolve() does not depend on this order,
    but stable order matters for reproducible audit output).
    """
    matched = []
    for rule in ruleset["rules"]:
        condition = rule.get("condition", {})
        if _rule_condition_matches(condition, action_proposal, risk_tier):
            matched.append(
                MatchedRule(
                    rule_id=rule["rule_id"],
                    effect=Effect[rule["effect"]],
                    approvable=rule["approvable"],
                    required_approver_roles=tuple(rule.get("required_approver_roles", [])),
                )
            )
    return matched
