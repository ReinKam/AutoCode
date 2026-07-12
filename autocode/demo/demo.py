"""
AutoCode MVP — end-to-end demo.

Walks a simulated Claude Agent SDK session through the full
canUseTool -> normalize -> match -> resolve -> PolicyDecision -> audit
chain, for the 6 scenarios that define the MVP demo:

    1. Read                          -> ALLOW
    2. Write /auth/**                -> BLOCK_REQUIRE_HIL
    3. HIL approval on that write    -> ALLOW (fresh PolicyDecision, not an extension)
    4. Delete audit log              -> BLOCK_DENY_PERMANENT (never overridable)
    5. Bash 'ls -la'                 -> BLOCK_REQUIRE_HIL (fail-closed default)
    6. An expired ALLOW ticket       -> rejected by capability validation

Nothing in this script executes a real file operation or shell command.
It only ever asks "would this be allowed", which is the entire point of
AutoCode's Policy Engine sitting in front of any Execution Backend.

Run: python3 demo.py
"""

import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "policy_engine"))
from can_use_tool_adapter import can_use_tool  # noqa: E402
from precedence import HilApproval  # noqa: E402
from capability import validate_capability  # noqa: E402
from audit_log import AuditLog  # noqa: E402

RULESET_PATH = os.path.join(os.path.dirname(__file__), "..", "policy_engine", "reference_ruleset.json")
with open(RULESET_PATH) as f:
    RULESET = json.load(f)


def banner(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def show(result):
    pd = result.policy_decision
    print(f"  behavior:      {result.behavior}")
    print(f"  decision:      {pd['decision']}")
    print(f"  risk_tier:     {pd['risk_tier']}")
    print(f"  reason_code:   {pd['reason_code']}")
    print(f"  matched_rules: {[r['rule_id'] for r in pd['matched_rules']]}")
    print(f"  expires_at:    {pd['expires_at']}")
    print(f"  sdk_result:    {result.sdk_permission_result}")
    return pd


def main():
    audit = AuditLog()

    banner("1. Read a file")
    r1 = can_use_tool("Read", {"file_path": "/readme.md"}, ruleset=RULESET, audit_log=audit)
    show(r1)
    assert r1.behavior == "ALLOW"

    banner("2. Write to /auth/** (no HIL yet)")
    r2 = can_use_tool("Write", {"file_path": "/auth/session.py"}, ruleset=RULESET, audit_log=audit)
    show(r2)
    assert r2.behavior == "BLOCK_REQUIRE_HIL"
    print("\n  -> Execution Backend must stop here. A human (security_reviewer) is asked to review.")

    banner("3. Same write, now WITH a valid security_reviewer HIL approval")
    approval = HilApproval(
        hil_decision_id="hil-demo-001",
        status="approved",
        approver_role="security_reviewer",
        targets_rule_ids=("AUTH_CHANGES_REQUIRE_HIL",),
    )
    r3 = can_use_tool(
        "Write", {"file_path": "/auth/session.py"}, ruleset=RULESET,
        hil_decisions=[approval], audit_log=audit,
        previous_decision_id=r2.policy_decision["policy_decision_id"],
    )
    pd3 = show(r3)
    assert r3.behavior == "ALLOW"
    print(f"\n  -> This is a NEW PolicyDecision (id={pd3['policy_decision_id'][:8]}...), "
          f"not an extension of decision {r2.policy_decision['policy_decision_id'][:8]}...")
    print(f"     Its own fresh TTL: {pd3['expires_at']}")

    banner("4. Delete the audit log")
    r4 = can_use_tool("Delete", {"file_path": "/audit_log/2026-07-09.jsonl"}, ruleset=RULESET, audit_log=audit)
    show(r4)
    assert r4.behavior == "BLOCK_DENY_PERMANENT"
    print("\n  -> deny_permanent. No HIL approval, however senior, can override this rule.")

    banner("5. Run a shell command ('ls -la')")
    r5 = can_use_tool("Bash", {"command": "ls -la"}, ruleset=RULESET, audit_log=audit)
    show(r5)
    assert r5.behavior == "BLOCK_REQUIRE_HIL"
    print("\n  -> Fail-closed MVP default: no rule explicitly allows run_command,")
    print("     so even a harmless command stops for HIL. This is a deliberate")
    print("     MVP policy choice, not a gap (see reference_ruleset.json).")

    banner("6. An expired capability ticket")
    r6 = can_use_tool("Read", {"file_path": "/notes.md"}, ruleset=RULESET, audit_log=audit)
    issued_at = r6.policy_decision["created_at"]
    print(f"  Ticket issued at {issued_at}, decision=ALLOW, TTL=5 minutes.")
    from datetime import datetime
    future = datetime.fromisoformat(issued_at) + timedelta(minutes=6)
    check = validate_capability(r6.policy_decision, r6.action_proposal, now=future)
    print(f"  Redeeming it 6 minutes later -> valid={check.valid}, reason_code={check.reason_code}")
    assert check.valid is False and check.reason_code == "EXPIRED"
    print("\n  -> Even though the original decision was ALLOW, the Execution Adapter")
    print("     must refuse: the capability ticket has expired and must be re-evaluated,")
    print("     never just re-used.")

    banner("Audit chain")
    print(f"  Total events recorded: {len(audit.events())}")
    print(f"  Chain intact (verify_chain()): {audit.verify_chain()}")
    assert audit.verify_chain() is True

    banner("Demo complete — all 6 scenarios behaved as specified.")


if __name__ == "__main__":
    main()
