"""
govern.py — the only sanctioned path from "I want to do X" to "X happened",
for this build. Every real file_write / run_command proposed while building
listapp goes through the actual, already-tested AutoCode Policy Engine —
not a reimplementation of it.

This does NOT execute anything itself. It only ever returns a verdict.
The caller (this chat session, acting as the execution backend) performs
the real action only when told ALLOW.
"""

import json
import os
import sys

AUTOCODE_ENGINE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "autocode", "policy_engine")
)
sys.path.insert(0, AUTOCODE_ENGINE_PATH)

from can_use_tool_adapter import can_use_tool  # noqa: E402
from precedence import HilApproval  # noqa: E402

RULESET_PATH = os.path.join(os.path.dirname(__file__), "ruleset.json")
AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.jsonl")

with open(RULESET_PATH) as f:
    RULESET = json.load(f)


def _append_audit_line(entry: dict) -> None:
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _last_event_hash() -> str:
    if not os.path.exists(AUDIT_LOG_PATH):
        return "0" * 64
    with open(AUDIT_LOG_PATH) as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    if not lines:
        return "0" * 64
    return json.loads(lines[-1])["event_hash"]


def propose(tool_name: str, tool_input: dict, hil_decisions=None, previous_decision_id=None):
    """
    Evaluates one real action against the real Policy Engine and persists
    the resulting PolicyDecision as a hash-chained AuditEvent on disk.
    Returns the AdapterResult — caller decides whether to actually act.
    """
    from canonical_hash import sha256_hex
    from datetime import datetime, timezone

    result = can_use_tool(
        tool_name,
        tool_input,
        ruleset=RULESET,
        proposed_by="claude-chat-session-as-execution-backend",
        hil_decisions=hil_decisions or [],
        previous_decision_id=previous_decision_id,
    )

    prev_hash = _last_event_hash()
    payload_hash = sha256_hex(result.policy_decision)
    timestamp = datetime.now(timezone.utc).isoformat()
    event_hash = sha256_hex({
        "event_type": "POLICY_DECISION_CREATED",
        "event_payload_hash": payload_hash,
        "previous_event_hash": prev_hash,
        "timestamp": timestamp,
    })
    _append_audit_line({
        "event_type": "POLICY_DECISION_CREATED",
        "event_payload_hash": payload_hash,
        "previous_event_hash": prev_hash,
        "event_hash": event_hash,
        "timestamp": timestamp,
        "policy_decision": result.policy_decision,
        "action_proposal": result.action_proposal,
    })

    return result


def make_hil_approval(hil_decision_id, status, approver_role, rule_id):
    return HilApproval(
        hil_decision_id=hil_decision_id,
        status=status,
        approver_role=approver_role,
        targets_rule_ids=(rule_id,),
    )
