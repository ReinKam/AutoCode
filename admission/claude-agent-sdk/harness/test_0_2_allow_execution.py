"""Gate 0 / Test 0.2 — allow -> exactly one real execution, matching input."""
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk.types import PermissionResultAllow

sys.path.insert(0, str(Path(__file__).parent))
from common import Verdict, canary_bash_command, event_stamp, execution_count, log, new_canary_token, require_api_key, require_cli_pinned  # noqa: E402

TEST_ID = "0.2"


async def main() -> Verdict:
    v = Verdict(test_id=TEST_ID, description="allow -> exactly one execution, input unchanged")
    cli_path = require_cli_pinned()
    token, canary_path = new_canary_token()
    cmd = canary_bash_command(token, canary_path)
    observed_inputs = []

    async def pre_tool_use_hook(input_data, tool_use_id, context):
        v.hook_calls += 1
        v.hook_called = True
        event_stamp(v.order, f"hook_called:{input_data.get('tool_name')}")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}

    async def can_use_tool(tool_name, input_data, context):
        v.callback_calls += 1
        v.callback_called = True
        observed_inputs.append(dict(input_data))
        event_stamp(v.order, f"callback_called:{tool_name}")
        return PermissionResultAllow(updated_input=input_data)

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
    matched = any(token in str(i.get("command", "")) for i in observed_inputs)
    v.notes = (
        f"PASS if hook_calls==1 and callback_calls==1 and execution_count_observed==1 "
        f"and executed command matched what the callback approved (matched={matched})"
    )
    return v


if __name__ == "__main__":
    require_api_key()
    log("0.2 starting")
    verdict = asyncio.run(main())
    log(f"hook_calls={verdict.hook_calls} callback_calls={verdict.callback_calls} execution_count={verdict.execution_count_observed}")
    verdict.emit()
