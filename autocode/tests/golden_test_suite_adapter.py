"""
Golden test suite for the canUseTool adapter.

Run: python3 golden_test_suite_adapter.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "policy_engine"))
from can_use_tool_adapter import can_use_tool  # noqa: E402
from precedence import HilApproval  # noqa: E402
from audit_log import AuditLog  # noqa: E402
from normalize import UnsupportedToolError  # noqa: E402

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


audit = AuditLog()

# 1. Read -> ALLOW
r1 = can_use_tool("Read", {"file_path": "/readme.md"}, ruleset=RULESET, audit_log=audit)
check("Read /readme.md -> ALLOW", r1.behavior == "ALLOW")
check("Read -> sdk_permission_result behavior 'allow'", r1.sdk_permission_result["behavior"] == "allow")

# 2. Write to /auth/session.py -> stub classifier elevates risk -> BLOCK_REQUIRE_HIL
r2 = can_use_tool("Write", {"file_path": "/auth/session.py"}, ruleset=RULESET, audit_log=audit)
check("Write /auth/session.py -> BLOCK_REQUIRE_HIL", r2.behavior == "BLOCK_REQUIRE_HIL")
check("BLOCK_* -> sdk_permission_result behavior 'deny'", r2.sdk_permission_result["behavior"] == "deny")

# 2b. Same write, but HIL approval with WRONG role -> still blocked
wrong_role_hil = HilApproval(
    hil_decision_id="hil-wrong-role",
    status="approved",
    approver_role="owner",
    targets_rule_ids=("AUTH_CHANGES_REQUIRE_HIL",),
)
r2b = can_use_tool(
    "Write", {"file_path": "/auth/session.py"}, ruleset=RULESET,
    hil_decisions=[wrong_role_hil], audit_log=audit,
    previous_decision_id=r2.policy_decision["policy_decision_id"],
)
check("Write /auth/session.py + owner approval (wrong role) -> still BLOCK_REQUIRE_HIL", r2b.behavior == "BLOCK_REQUIRE_HIL")

# 2c. Same write, correct role -> ALLOW
correct_hil = HilApproval(
    hil_decision_id="hil-correct-role",
    status="approved",
    approver_role="security_reviewer",
    targets_rule_ids=("AUTH_CHANGES_REQUIRE_HIL",),
)
r2c = can_use_tool(
    "Write", {"file_path": "/auth/session.py"}, ruleset=RULESET,
    hil_decisions=[correct_hil], audit_log=audit,
    previous_decision_id=r2.policy_decision["policy_decision_id"],
)
check("Write /auth/session.py + security_reviewer approval -> ALLOW", r2c.behavior == "ALLOW")
check("ALLOW -> matched_rules records overridden=True for AUTH rule",
      any(mr["rule_id"] == "AUTH_CHANGES_REQUIRE_HIL" and mr["overridden"] for mr in r2c.policy_decision["matched_rules"]))

# 3. Write to unrelated path, no elevation, no matching rule -> BLOCK_REQUIRE_HIL
#    (fail-closed MVP decision: NO_RULES_MATCHED -> require_hil, not allow.
#    Only explicit allow rules like READ_ONLY_ACTIONS_ALLOWED permit by default.)
r3 = can_use_tool("Write", {"file_path": "/billing/report.py"}, ruleset=RULESET, audit_log=audit)
check("Write /billing/report.py (medium risk, no matching rule) -> BLOCK_REQUIRE_HIL (fail-closed)", r3.behavior == "BLOCK_REQUIRE_HIL")

# 4. Delete /audit_log/** -> BLOCK_DENY_PERMANENT, and NOT overridable even with an approval attempt
r4 = can_use_tool("Delete", {"file_path": "/audit_log/2026-07-09.jsonl"}, ruleset=RULESET, audit_log=audit)
check("Delete /audit_log/... -> BLOCK_DENY_PERMANENT", r4.behavior == "BLOCK_DENY_PERMANENT")

owner_attempt = HilApproval(
    hil_decision_id="hil-attempt-override-permanent",
    status="approved",
    approver_role="owner",
    targets_rule_ids=("DELETE_AUDIT_LOG",),
)
r4b = can_use_tool(
    "Delete", {"file_path": "/audit_log/2026-07-09.jsonl"}, ruleset=RULESET,
    hil_decisions=[owner_attempt], audit_log=audit,
)
check("Delete /audit_log/... + approval attempt -> STILL BLOCK_DENY_PERMANENT (non-overridable)", r4b.behavior == "BLOCK_DENY_PERMANENT")

# 5. run_command destructive -> BLOCK_REQUIRE_HIL, then owner approval -> ALLOW
r5 = can_use_tool("Bash", {"command": "rm -rf /data/tmp"}, ruleset=RULESET, audit_log=audit)
check("Bash 'rm -rf /data/tmp' -> BLOCK_REQUIRE_HIL", r5.behavior == "BLOCK_REQUIRE_HIL")

owner_hil = HilApproval(
    hil_decision_id="hil-owner-approves-command",
    status="approved",
    approver_role="owner",
    targets_rule_ids=("DESTRUCTIVE_COMMAND_REQUIRES_HIL",),
)
r5b = can_use_tool(
    "Bash", {"command": "rm -rf /data/tmp"}, ruleset=RULESET,
    hil_decisions=[owner_hil], audit_log=audit,
    previous_decision_id=r5.policy_decision["policy_decision_id"],
)
check("Bash 'rm -rf /data/tmp' + owner approval -> ALLOW", r5b.behavior == "ALLOW")

# 6. run_command benign, but no explicit allow rule covers run_command -> BLOCK_REQUIRE_HIL (fail-closed)
r6 = can_use_tool("Bash", {"command": "ls -la"}, ruleset=RULESET, audit_log=audit)
check("Bash 'ls -la' -> BLOCK_REQUIRE_HIL (no explicit allow rule for run_command, fail-closed default)", r6.behavior == "BLOCK_REQUIRE_HIL")

# 7. Git operations explicitly out of scope -> adapter refuses to guess, raises
try:
    can_use_tool("git_push", {"target_branch": "main"}, ruleset=RULESET)
    check("git_push raises UnsupportedToolError (out of scope for this adapter version)", False)
except UnsupportedToolError:
    check("git_push raises UnsupportedToolError (out of scope for this adapter version)", True)

# 8. Unknown/unmapped tool_name -> refuses to guess, raises
try:
    can_use_tool("SomeFutureTool", {}, ruleset=RULESET)
    check("Unmapped tool_name raises UnsupportedToolError (no guessing)", False)
except UnsupportedToolError:
    check("Unmapped tool_name raises UnsupportedToolError (no guessing)", True)

# 9. Adapter never executes anything: AdapterResult carries only data, no callables
non_data_fields = [
    f for f in ("behavior", "action_proposal", "policy_decision", "sdk_permission_result")
    if callable(getattr(r1, f))
]
check("AdapterResult exposes only data fields, nothing callable/executable", non_data_fields == [])

# 10. Audit chain integrity: verify_chain() true after N calls, false after tampering
check("Audit chain intact after all adapter calls", audit.verify_chain())
tampered = AuditLog()
tampered._events = [dict(e) for e in audit.events()]
tampered._last_hash = audit._last_hash
if tampered._events:
    tampered._events[0]["event_payload_hash"] = "0" * 64  # simulate retroactive tampering
check("Audit chain detects tampering (verify_chain() -> False after mutation)", tampered.verify_chain() is False)

check("Audit log recorded exactly one POLICY_DECISION_CREATED event per adapter call", len(audit.events()) == 10)


print()
failures = [name for status, name in results_log if status == "FAIL"]
if failures:
    print(f"{len(failures)} of {len(results_log)} adapter golden cases FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
else:
    print(f"All {len(results_log)} adapter golden cases passed.")
