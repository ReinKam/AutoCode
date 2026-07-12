"""
Canonical serialization + hashing.

Every hash in AutoCode (ActionProposal.input_hash reference,
PolicyDecision.decision_hash, AuditEvent.event_hash) must be reproducible
byte-for-byte given the same logical content, regardless of key insertion
order, whitespace, or JSON library defaults. This module is the single
place that defines "canonical" so every other component agrees.

Pure function. No I/O.
"""

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """
    Deterministic JSON serialization:
      - keys sorted recursively
      - no insignificant whitespace
      - fixed separators
      - UTF-8, no ASCII escaping quirks (ensure_ascii=False + explicit encode)
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(obj: Any) -> str:
    canonical = canonical_json(obj)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
