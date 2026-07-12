"""
TTL policy for PolicyDecision.expires_at.

Every PolicyDecision gets a concrete expires_at — never null. This keeps
the downstream invariant simple: "is this ticket still valid" is always
a plain timestamp comparison, with no branch for "decisions that never
expire". deny_permanent gets a real (if distant) timestamp instead of a
null special-case, exactly so nothing downstream has to special-case it.

TTLs, as agreed:
    allow               -> 5 minutes
    require_hil         -> 15 minutes
    deny_until_changed  -> 24 hours
    deny_permanent      -> far-future sentinel; re-evaluated on any new
                            ActionProposal regardless, since deny_permanent
                            is keyed to the rule, not to this ticket.

Pure function. No I/O, no wall-clock reads (caller supplies `created_at`).
"""

from datetime import datetime, timedelta

TTL_BY_DECISION = {
    "allow": timedelta(minutes=5),
    "require_hil": timedelta(minutes=15),
    "deny_until_changed": timedelta(hours=24),
}

# Concrete, not null — see module docstring for why.
DENY_PERMANENT_EXPIRES_AT = "9999-12-31T23:59:59+00:00"


class UnknownDecisionTypeError(ValueError):
    pass


def compute_expires_at(decision: str, created_at: datetime) -> str:
    if decision == "deny_permanent":
        return DENY_PERMANENT_EXPIRES_AT

    ttl = TTL_BY_DECISION.get(decision)
    if ttl is None:
        raise UnknownDecisionTypeError(
            f"No TTL policy defined for decision='{decision}'. "
            f"Refusing to guess a lifetime for an unrecognized decision type."
        )
    return (created_at + ttl).isoformat()
