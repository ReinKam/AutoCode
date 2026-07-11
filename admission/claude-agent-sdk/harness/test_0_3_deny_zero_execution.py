"""Gate 0 / Test 0.3 — deny -> zero execution, side effect never exists."""
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk.types import PermissionResultDeny

sys.path.insert(0, str(Path(__file__).parent))
from common import Verdict, canary_bash_command, event_stamp, execution_count, log, new_canary_token, require_api_key, require_cli_pinned  # noqa: E402

TEST_ID = "0.3"


async def main() -> Verdict:
    v = Verdict(test_id=TEST_ID, description="deny -> zero execution, side effect must not exist")
    cli_path = require_cli_pinned()
    token, canary_path = new_canary_token()
    cmd = canary_bash_command(token, canary_path)

    async def pre_tool_use_hook(input_data, tool_use_id, context):
        v.hook_calls += 1
        v.hook_called = True
        event_stamp(v.order, "hook_called")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}

    async def can_use_tool(tool_name, input_data, context):
        v.callback_calls += 1
        v.callback_called = True
        event_stamp(v.order, "callback_called")
        return PermissionResultDeny(message="0.3: denied by design")

    options = ClaudeAgentOptions(
        cli_path=cli_path,
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(hooks=[pre_tool_use_hook])]},
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
    v.notes = "PASS if execution_count_observed==0 and canary file does not exist at all"
    return v


if __name__ == "__main__":
    require_api_key()
    log("0.3 starting")
    verdict = asyncio.run(main())
    log(f"execution_count={verdict.execution_count_observed}")
    verdict.emit()
