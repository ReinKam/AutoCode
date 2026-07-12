"""
Risk Classifier — v0 STUB.

This is a deliberately minimal, deterministic placeholder so the
canUseTool adapter can be wired and tested end-to-end today. It is NOT
the final Risk Classifier design (that is a separate future component
with its own spec, signals, and golden tests). It is pinned to its own
version string precisely so it can be swapped later without touching
the adapter contract or the PolicyDecision schema.

Pure function. No LLM calls, no I/O. "Unknown" is intentionally never
returned by this stub for the 4 supported action_types — a real
classifier is expected to actually produce 'unknown' when it lacks
signal; this stub always has an opinion, which is itself a limitation
worth fixing when the real classifier is built.
"""

import fnmatch
from typing import Tuple

RISK_CLASSIFIER_VERSION = "0.0.1-stub"

_BASE_TIER_BY_ACTION_TYPE = {
    "file_read": "low",
    "file_write": "medium",
    "file_delete": "high",
    "run_command": "medium",
}

_SENSITIVE_PATH_PATTERNS = ("/auth/**", "/secrets/**", "/audit_log/**", "/var/autocode/**")

_DESTRUCTIVE_COMMAND_SUBSTRINGS = ("rm -rf", "rm -r ", "sudo ", "chmod 777", "curl | sh", "> /dev/")

_TIER_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_RANK_TIER = {v: k for k, v in _TIER_RANK.items()}


def _elevate(tier: str, floor: str) -> str:
    return _RANK_TIER[max(_TIER_RANK[tier], _TIER_RANK[floor])]


def classify_risk(action_proposal: dict) -> Tuple[str, str, list]:
    """
    Returns (risk_tier, risk_classifier_version, signals).
    """
    action_type = action_proposal.get("action_type")
    tier = _BASE_TIER_BY_ACTION_TYPE.get(action_type)
    signals = []

    if tier is None:
        # Unsupported action_type for this stub -> force maximum caution,
        # not a guess. Real classifier should replace this with 'unknown'.
        return "critical", RISK_CLASSIFIER_VERSION, ["UNSUPPORTED_ACTION_TYPE_STUB_FALLBACK"]

    signals.append(f"BASE_TIER_FOR_{action_type.upper()}")

    paths = action_proposal.get("paths") or []
    if any(fnmatch.fnmatch(p, pat) for p in paths for pat in _SENSITIVE_PATH_PATTERNS):
        tier = _elevate(tier, "high")
        signals.append("PATH_MATCHES_SENSITIVE_PATTERN")

    if action_type == "run_command":
        command = (action_proposal.get("payload") or {}).get("command", "")
        if any(s in command for s in _DESTRUCTIVE_COMMAND_SUBSTRINGS):
            tier = _elevate(tier, "high")
            signals.append("COMMAND_MATCHES_DESTRUCTIVE_PATTERN")

    return tier, RISK_CLASSIFIER_VERSION, signals
