"""
Golden test suite for TTL policy + capability validation.

Run: python3 golden_test_suite_ttl.py
"""

import json
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "policy_engine"))
from ttl_policy import compute_expires_at, DENY_PERMANENT_EXPIRES_AT  # noqa: E402
from capability import validate_capability  # noqa: E402
from can_use_tool_adapter import can_use_tool  # noqa: E402
from precedence import HilApproval  # noqa: E402

REFERENCE_RULESET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "policy_engine", "reference_ruleset.json"
)
with open(REFERENCE_RULESET_PATH) as f:
    RULESET = json.load(f)

results_log = []


def check(name, condition):
    status = "PASS" if condition else "FAIL"
    results_log.append((status, name))
    print(f"[{status}] {name}")


T0 = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)

# 1-4: TTL per decision type, exact deltas
check(
    "allow -> expires 5 minutes after created_at",
    compute_expires_at("allow", T0) == (T0 + timedelta(minutes=5)).isoformat(),
)
check(
    "require_hil -> expires 15 minutes after created_at",
    compute_expires_at("require_hil", T0) == (T0 + timedelta(minutes=15)).isoformat(),
)
check(
    "deny_until_changed -> expires 24 hours after created_at",
    compute_expires_at("deny_until_changed", T0) == (T0 + timedelta(hours=24)).isoformat(),
)
check(
    "deny_permanent -> far-future sentinel, independent of created_at",
    compute_expires_at("deny_permanent", T0) == DENY_PERMANENT_EXPIRES_AT,
)

# 5: valid, fresh capability -> VALID
r1 = can_use_tool("Read", {"file_path": "/readme.md"}, ruleset=RULESET)
check_now = datetime.fromisoformat(r1.policy_decision["created_at"]) + timedelta(seconds=1)
result5 = validate_capability(r1.policy_decision, r1.action_proposal, now=check_now)
check("Fresh ALLOW ticket, checked 1s later -> VALID", result5.valid and result5.reason_code == "VALID")

# 6: expired capability -> EXPIRED
expired_check_now = datetime.fromisoformat(r1.policy_decision["created_at"]) + timedelta(minutes=6)
result6 = validate_capability(r1.policy_decision, r1.action_proposal, now=expired_check_now)
check(
    "Same ALLOW ticket, checked 6 minutes later (TTL=5min) -> EXPIRED",
    not result6.valid and result6.reason_code == "EXPIRED",
)

# 7: tampered proposal -> INPUT_HASH_MISMATCH
tampered_proposal = dict(r1.action_proposal)
tampered_proposal["paths"] = ["/etc/shadow"]  # changed after the ticket was issued
result7 = validate_capability(r1.policy_decision, tampered_proposal, now=check_now)
check(
    "ALLOW ticket checked against a modified ActionProposal -> INPUT_HASH_MISMATCH",
    not result7.valid and result7.reason_code == "INPUT_HASH_MISMATCH",
)

# 8: a require_hil ticket is never itself a valid capability, even if unexpired
r8 = can_use_tool("Write", {"file_path": "/auth/x.py"}, ruleset=RULESET)
result8 = validate_capability(r8.policy_decision, r8.action_proposal, now=check_now)
check(
    "require_hil ticket -> DECISION_NOT_ALLOW (never directly executable, regardless of expiry)",
    not result8.valid and result8.reason_code == "DECISION_NOT_ALLOW",
)

# 9: HIL approval never extends the old ticket — it produces a brand new one
#    with its OWN fresh TTL, not the old ticket's remaining/extended lifetime.
v1 = can_use_tool("Write", {"file_path": "/auth/y.py"}, ruleset=RULESET)
approval = HilApproval(
    hil_decision_id="hil-ttl-test",
    status="approved",
    approver_role="security_reviewer",
    targets_rule_ids=("AUTH_CHANGES_REQUIRE_HIL",),
)
v2 = can_use_tool(
    "Write", {"file_path": "/auth/y.py"}, ruleset=RULESET,
    hil_decisions=[approval],
    previous_decision_id=v1.policy_decision["policy_decision_id"],
)
v1_expires = datetime.fromisoformat(v1.policy_decision["expires_at"])
v2_expires = datetime.fromisoformat(v2.policy_decision["expires_at"])
v2_created = datetime.fromisoformat(v2.policy_decision["created_at"])
check(
    "v2 (post-HIL, allow) expires_at == v2's OWN created_at + 5min (fresh TTL, not inherited)",
    v2_expires == v2_created + timedelta(minutes=5),
)
check(
    "v2 expires_at is earlier than v1's original 15-min require_hil expiry (proves no extension occurred)",
    v2_expires < v1_expires,
)
check(
    "v1 and v2 are distinct PolicyDecisions",
    v1.policy_decision["policy_decision_id"] != v2.policy_decision["policy_decision_id"],
)

# 10: deny_permanent ticket is never valid, and its expires_at is the far-future sentinel
r10 = can_use_tool("Delete", {"file_path": "/audit_log/x.jsonl"}, ruleset=RULESET)
result10 = validate_capability(r10.policy_decision, r10.action_proposal, now=check_now)
check(
    "deny_permanent ticket -> DECISION_NOT_ALLOW, and expires_at uses the far-future sentinel",
    not result10.valid
    and result10.reason_code == "DECISION_NOT_ALLOW"
    and r10.policy_decision["expires_at"] == DENY_PERMANENT_EXPIRES_AT,
)


print()
failures = [name for status, name in results_log if status == "FAIL"]
if failures:
    print(f"{len(failures)} of {len(results_log)} TTL/capability golden cases FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
else:
    print(f"All {len(results_log)} TTL/capability golden cases passed.")
