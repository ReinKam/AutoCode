"""
common.py — shared plumbing for the Claude Agent SDK admission test harness
(AutoCode ADR 0002 — Admission Gate 0).

Design constraints this file exists to satisfy:

  * Prove REAL side effects, not just callback logs. Every test verifies an
    actual, observable artifact (a counter file incremented by the CLI's
    own Bash tool), because a hook/callback log can look correct while the
    SDK still executes the tool underneath.

  * Pin the EXACT binary. `cli_path` is passed explicitly, pointing at the
    bundled binary whose SHA-256 is recorded in admission_note.md, so no
    test result is contaminated by "which claude did it actually run".

  * Machine-readable output. Every test prints exactly one JSON line to
    stdout at the end: the verdict. Human-readable narration goes to
    stderr so stdout can be parsed/diffed mechanically.

This module does NOT import any AutoCode policy code. Per the agreed
sequencing, Gate 0 characterizes the SDK contract in isolation first.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

HARNESS_DIR = Path(__file__).parent
BUNDLED_CLI = (
    HARNESS_DIR.parent.parent.parent
    / "venv"
    / "lib"
    / "python3.12"
    / "site-packages"
    / "claude_agent_sdk"
    / "_bundled"
    / "claude"
)
CANARY_DIR = HARNESS_DIR / "_canary"
CANARY_DIR.mkdir(exist_ok=True)


def log(msg: str) -> None:
    """Human-readable narration -> stderr, keeps stdout clean for the verdict."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def require_cli_pinned() -> str:
    if not BUNDLED_CLI.exists():
        raise SystemExit(
            f"Pinned CLI not found at {BUNDLED_CLI}. "
            "Run `pip install claude-agent-sdk` in venv/ first, per admission_note.md."
        )
    return str(BUNDLED_CLI)


def require_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. This test drives a real query() session "
            "and cannot run without it. See admission_note.md 'Execution constraint'. "
            "Run this script in an authenticated environment and paste the JSON "
            "verdict line back."
        )


def new_canary_token() -> tuple[str, Path]:
    """A fresh, unique token + the file path a tool call would need to touch
    to prove it actually ran. Unique per test invocation so stale artifacts
    from a previous run can never produce a false positive."""
    token = uuid.uuid4().hex
    path = CANARY_DIR / f"canary_{token}.txt"
    return token, path


def canary_bash_command(token: str, path: Path) -> str:
    """The exact shell command a Bash tool call would need to run to prove
    execution. Deliberately trivial and side-effect-scoped to CANARY_DIR."""
    return f"echo {token} >> {path}"


def execution_count(path: Path, token: str) -> int:
    """How many times the canary side effect actually landed on disk."""
    if not path.exists():
        return 0
    return path.read_text().count(token)


@dataclass
class Verdict:
    test_id: str
    description: str
    hook_called: bool = False
    hook_calls: int = 0
    callback_called: bool = False
    callback_calls: int = 0
    execution_count_observed: int = 0
    order: list[str] = field(default_factory=list)
    sdk_exception: str | None = None
    process_outcome: str = "unknown"  # completed | crashed | hung_then_timed_out | cancelled
    notes: str = ""

    def emit(self) -> None:
        print(json.dumps(self.__dict__, sort_keys=True))


def event_stamp(order: list[str], name: str) -> None:
    order.append(f"{time.monotonic():.6f}:{name}")
