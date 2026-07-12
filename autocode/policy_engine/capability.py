"""
Capability ticket validation.

A PolicyDecision only functions as a capability ticket if something
actually enforces its three conditions before execution:
    1. decision == 'allow'
    2. not expired (now < expires_at)
    3. input_hash still matches the ActionProposal being acted on
       (catches drift/tampering between issuance and execution)

This is deliberately separate from can_use_tool_adapter — this is the
check a future Execution Adapter Layer calls right before it actually
invokes Claude Agent SDK / Hermes / OpenClaw etc. can_use_tool_adapter
issues tickets; this module redeems them.

Pure function. No I/O, no wall-clock reads (caller supplies `now`).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from canonical_hash import sha256_hex


@dataclass(frozen=True)
class CapabilityCheck:
    valid: bool
    reason_code: str


def validate_capability(
    policy_decision: dict,
    action_proposal: dict,
    now: Optional[datetime] = None,
) -> CapabilityCheck:
    now = now or datetime.now(timezone.utc)

    if policy_decision["decision"] != "allow":
        return CapabilityCheck(False, "DECISION_NOT_ALLOW")

    expires_at = datetime.fromisoformat(policy_decision["expires_at"])
    if now >= expires_at:
        return CapabilityCheck(False, "EXPIRED")

    if policy_decision["input_hash"] != sha256_hex(action_proposal):
        return CapabilityCheck(False, "INPUT_HASH_MISMATCH")

    return CapabilityCheck(True, "VALID")
