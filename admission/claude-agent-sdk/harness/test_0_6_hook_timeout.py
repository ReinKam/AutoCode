"""Gate 0 / Test 0.6 — PreToolUse hook exceeds its timeout -> zero execution.

Uses a short, explicit HookMatcher(timeout=...) and a hook that sleeps
longer than that timeout, per the admission spec.
"""
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

sys.path.insert(0, str(Path(__file__).parent))
from common import Verdict, canary_bash_command, event_stamp, execution_count, log, new_canary_token, require_api_key, require_cli_pinned  # noqa: E402

TEST_ID = "0.6"
SHORT_TIMEOUT_SECONDS = 3
HOOK_SLEEP_SECONDS = 15


async def main() -> Verdict:
    v = Verdict(test_id=TEST_ID, description="hook exceeds timeout -> zero execution")
    cli_path = require_cli_pinned()
    token, canary_path = new_canary_token()
    cmd = canary_bash_command(token, canary_path)

    async def slow_hook(input_data, tool_use_id, context):
        v.hook_calls += 1
        v.hook_called = True
        event_stamp(v.order, "hook_called_then_sleeping")
        await asyncio.sleep(HOOK_SLEEP_SECONDS)
        # Should never be reached if the SDK enforces the timeout.
        event_stamp(v.order, "hook_woke_up_after_sleep")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"}}

    options = ClaudeAgentOptions(
        cli_path=cli_path,
        hooks={
            "PreToolUse": [
                HookMatcher(hooks=[slow_hook], timeout=SHORT_TIMEOUT_SECONDS)
            ]
        },
        permission_mode="default",
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(f"Run this exact shell command using the Bash tool, nothing else: {cmd}")
            async for _m in client.receive_response():
                pass
        v.process_outcome = "completed"
    except Exception as e:  # noqa: BLE001
        v.sdk_exception = f"{type(e).__name__}: {e}"
        v.process_outcome = "crashed"

    v.execution_count_observed = execution_count(canary_path, token)
    v.notes = (
        f"HARD REQUIREMENT: execution_count_observed==0, hook timeout={SHORT_TIMEOUT_SECONDS}s, "
        f"hook sleeps {HOOK_SLEEP_SECONDS}s. Check order[] for whether the hook actually got "
        "cut off (no 'hook_woke_up_after_sleep' event) or ran to completion anyway."
    )
    return v


if __name__ == "__main__":
    require_api_key()
    log("0.6 starting")
    verdict = asyncio.run(main())
    log(f"execution_count={verdict.execution_count_observed} order={verdict.order}")
    verdict.emit()
