"""
Minimal in-memory, hash-chained Audit Log — matches audit_event.schema.json.

This is a reference implementation for wiring/testing purposes. A
production AutoCode deployment would back this with durable, append-only
storage (and likely external anchoring), but the chaining logic itself
does not change: that's the point of separating it out as a pure,
testable unit here.
"""

import uuid
from datetime import datetime, timezone

from canonical_hash import sha256_hex

GENESIS_HASH = "0" * 64


class AuditLog:
    def __init__(self):
        self._events = []
        self._last_hash = GENESIS_HASH

    def record(self, event_type: str, payload: dict, correlation: dict = None) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_hash = sha256_hex(payload)
        event_core = {
            "event_type": event_type,
            "event_payload_hash": payload_hash,
            "previous_event_hash": self._last_hash,
            "timestamp": timestamp,
        }
        event_hash = sha256_hex(event_core)
        event = {
            "audit_event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "correlation": correlation or {},
            "event_payload_hash": payload_hash,
            "previous_event_hash": self._last_hash,
            "event_hash": event_hash,
            "timestamp": timestamp,
        }
        self._events.append(event)
        self._last_hash = event_hash
        return event

    def verify_chain(self) -> bool:
        """Recomputes every event_hash from scratch and confirms the chain
        has not been tampered with. Pure re-derivation, no trust in stored
        event_hash values."""
        expected_previous = GENESIS_HASH
        for event in self._events:
            if event["previous_event_hash"] != expected_previous:
                return False
            recomputed = sha256_hex({
                "event_type": event["event_type"],
                "event_payload_hash": event["event_payload_hash"],
                "previous_event_hash": event["previous_event_hash"],
                "timestamp": event["timestamp"],
            })
            if recomputed != event["event_hash"]:
                return False
            expected_previous = event["event_hash"]
        return True

    def events(self) -> list:
        return list(self._events)
