"""
Golden test suite for the Rule Matcher (+ canonical hashing, + end-to-end
integration with precedence.resolve()).

Run: python3 golden_test_suite_matcher.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "policy_engine"))
from rule_matcher import match_rules  # noqa: E402
from precedence import Effect, HilApproval, resolve  # noqa: E402
from canonical_hash import canonical_json, sha256_hex  # noqa: E402

REFERENCE_RULESET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "policy_engine", "reference_ruleset.json"
)
with open(REFERENCE_RULESET_PATH) as f:
    RULESET = json.load(f)


def proposal(action_type, paths=None, target_branch=None, action_proposal_id="ap-001"):
    return {
        "action_proposal_id": action_proposal_id,
        "action_type": action_type,
        "proposed_by": "claude-agent-sdk",
        "paths": paths or [],
        "target_branch": target_branch,
        "payload": {},
        "created_at": "2026-07-09T17:00:00Z",
    }


CASES = []
results_log = []


def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results_log.append((status, name))
    print(f"[{status}] {name}")


# 1. file_write under /auth/** at high risk -> matches AUTH_CHANGES_REQUIRE_HIL
p1 = proposal("file_write", paths=["/auth/login.py"])
m1 = match_rules(p1, "high", RULESET)
check(
    "file_write /auth/login.py @ high -> matches AUTH_CHANGES_REQUIRE_HIL",
    any(r.rule_id == "AUTH_CHANGES_REQUIRE_HIL" for r in m1),
)

# 2. file_write outside /auth -> does not match
p2 = proposal("file_write", paths=["/billing/invoice.py"])
m2 = match_rules(p2, "high", RULESET)
check(
    "file_write /billing/invoice.py @ high -> AUTH rule does NOT match",
    not any(r.rule_id == "AUTH_CHANGES_REQUIRE_HIL" for r in m2),
)

# 3. multiple paths, only one under /auth/** -> still matches (ANY semantics)
p3 = proposal("file_write", paths=["/billing/invoice.py", "/auth/session.py"])
m3 = match_rules(p3, "critical", RULESET)
check(
    "mixed paths incl. one /auth/** path @ critical -> matches (ANY-path semantics)",
    any(r.rule_id == "AUTH_CHANGES_REQUIRE_HIL" for r in m3),
)

# 4. path matches but risk_tier does not -> AND semantics means no match
p4 = proposal("file_write", paths=["/auth/session.py"])
m4 = match_rules(p4, "low", RULESET)
check(
    "file_write /auth/session.py @ low risk -> AUTH rule does NOT match (AND across fields)",
    not any(r.rule_id == "AUTH_CHANGES_REQUIRE_HIL" for r in m4),
)

# 5. rule with no path_matches (READ_ONLY_ACTIONS_ALLOWED) -> unrestricted by path
p5 = proposal("file_read", paths=["/anything/at/all.py"])
m5 = match_rules(p5, "critical", RULESET)
check(
    "file_read any path @ critical -> matches READ_ONLY_ACTIONS_ALLOWED (no path constraint)",
    any(r.rule_id == "READ_ONLY_ACTIONS_ALLOWED" for r in m5),
)

# 6. target_branch glob: release/* matches release/1.2, not main
p6a = proposal("git_push", target_branch="release/1.2")
p6b = proposal("git_push", target_branch="develop")
m6a = match_rules(p6a, "medium", RULESET)
m6b = match_rules(p6b, "medium", RULESET)
check(
    "git_push to release/1.2 -> matches NO_PUSH_MAIN_WITHOUT_HIL (glob release/*)",
    any(r.rule_id == "NO_PUSH_MAIN_WITHOUT_HIL" for r in m6a),
)
check(
    "git_push to develop -> does NOT match NO_PUSH_MAIN_WITHOUT_HIL",
    not any(r.rule_id == "NO_PUSH_MAIN_WITHOUT_HIL" for r in m6b),
)

# 7. git_push to main -> matches
p7 = proposal("git_push", target_branch="main")
m7 = match_rules(p7, "medium", RULESET)
check(
    "git_push to main -> matches NO_PUSH_MAIN_WITHOUT_HIL",
    any(r.rule_id == "NO_PUSH_MAIN_WITHOUT_HIL" for r in m7),
)

# 8. file_delete under /audit_log/** -> matches DELETE_AUDIT_LOG regardless of risk_tier
p8 = proposal("file_delete", paths=["/audit_log/2026-07-09.jsonl"])
m8 = match_rules(p8, "low", RULESET)
check(
    "file_delete /audit_log/** @ low risk -> matches DELETE_AUDIT_LOG (no risk_tiers constraint on rule)",
    any(r.rule_id == "DELETE_AUDIT_LOG" for r in m8),
)

# 9. canonical hash determinism: same content, different key order -> same hash
obj_a = {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}}
obj_b = {"a": 1, "nested": {"x": 1, "y": 2}, "b": 2}
check(
    "canonical_json/sha256_hex identical for reordered-but-equal dicts",
    sha256_hex(obj_a) == sha256_hex(obj_b) and canonical_json(obj_a) == canonical_json(obj_b),
)
check(
    "canonical_json differs for genuinely different content",
    sha256_hex(obj_a) != sha256_hex({**obj_a, "b": 3}),
)

# 10. End-to-end: proposal -> match_rules -> resolve() for auth change + HIL approval
p10 = proposal("file_write", paths=["/auth/session.py"])
m10 = match_rules(p10, "high", RULESET)
r10_no_hil = resolve(matched_rules=m10, hil_decisions=[], risk_tier="high")
check(
    "end-to-end: auth file_write @ high, no HIL -> require_hil",
    r10_no_hil.decision == Effect.require_hil,
)

hil_approval = HilApproval(
    hil_decision_id="hil-e2e-1",
    status="approved",
    approver_role="security_reviewer",
    targets_rule_ids=("AUTH_CHANGES_REQUIRE_HIL",),
)
r10_with_hil = resolve(matched_rules=m10, hil_decisions=[hil_approval], risk_tier="high")
check(
    "end-to-end: auth file_write @ high, valid security_reviewer HIL -> allow",
    r10_with_hil.decision == Effect.allow,
)

# 11. End-to-end: unknown risk short-circuits the matcher entirely (structural guarantee)
p11 = proposal("file_read", paths=["/readme.md"])
m11 = match_rules(p11, "unknown", RULESET)  # matcher still runs (harmless)
r11 = resolve(matched_rules=m11, hil_decisions=[], risk_tier="unknown")
check(
    "end-to-end: even a harmless file_read @ unknown risk -> require_hil (structural guarantee holds regardless of matched_rules)",
    r11.decision == Effect.require_hil and r11.reason_code == "UNKNOWN_RISK_TIER",
)


print()
failures = [name for status, name in results_log if status == "FAIL"]
if failures:
    print(f"{len(failures)} of {len(results_log)} matcher golden cases FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
else:
    print(f"All {len(results_log)} matcher golden cases passed.")
