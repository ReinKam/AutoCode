"""
Gate 0 / Test 0.10a — static check, runnable right now without any API key
or live session: `sdk_governance.py` (once it exists) must never construct
a PermissionResultAllow with updated_permissions set to anything other than
None. Persisting SDK-level permissions would let one human approval create
a standing bypass of the hook/callback for later, structurally similar
calls -- exactly the invariant ADR 0002's "0.10 second level" cares about.

This is a source-level grep, not a type-checker -- it is a fast, cheap
tripwire, not a substitute for 0.10b (end-to-end).
"""
import json
import re
import sys
from pathlib import Path

TARGET = Path(__file__).parent.parent.parent / "sdk_governance.py"

VIOLATION_PATTERN = re.compile(
    r"updated_permissions\s*=\s*(?!None\b)"
)


def main() -> dict:
    result = {
        "test_id": "0.10a",
        "description": "static: sdk_governance.py never sets updated_permissions to a non-None value",
    }
    if not TARGET.exists():
        result["status"] = "not_applicable_yet"
        result["notes"] = (
            f"{TARGET} does not exist yet -- sdk_governance.py has not been written. "
            "This test is a tripwire for that file once it's created; re-run it after "
            "sdk_governance.py exists and before treating 0.10 as satisfied."
        )
        return result

    source = TARGET.read_text()
    violations = [
        (i + 1, line)
        for i, line in enumerate(source.splitlines())
        if VIOLATION_PATTERN.search(line)
    ]
    result["status"] = "fail" if violations else "pass"
    result["violations"] = violations
    result["notes"] = (
        "PASS if no line sets updated_permissions to anything but None. "
        "This does not prove the runtime never does it via indirection -- see 0.10b."
    )
    return result


if __name__ == "__main__":
    verdict = main()
    print(json.dumps(verdict, sort_keys=True))
