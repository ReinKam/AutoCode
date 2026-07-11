"""
Gate 0 / Test 0.10b — end-to-end: does approving one call ever cause a later,
structurally similar call in the SAME session to skip the hook/callback?

AutoCode's own callback never sets updated_permissions (0.10a covers that),
but this test checks the SDK's own behavior independent of our code: if we
never opt in, does a second matching Bash call still get routed through the
hook and callback exactly like the first one did?
"""
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk.types import PermissionResultAllow

sys.path.insert(0, str(Path(__file__).parent))
from common import Verdict, canary_bash_command, event_stamp, execution_count, log, new_canary_token, require_api_key, require_cli_pinned  # noqa: E402

TEST_ID = "0.10b"


async def main() -> Verdict:
    v = Verdict(test_id=TEST_ID, description="approving call #1 must not bypass hook/callback for call #2")
    cli_path = require_cli_pinned()
    token1, canary1 = new_canary_token()
    token2, canary2 = new_canary_token()
    cmd1 = canary_bash_command(token1, canary1)
    cmd2 = canary_bash_command(token2, canary2)

    async def pre_tool_use_hook(input_data, tool_use_id, context):
        v.hook_calls += 1
        v.hook_called = True
        event_stamp(v.order, f"hook_called:{tool_use_id}")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}

    async def can_use_tool(tool_name, input_data, context):
        v.callback_calls += 1
        v.callback_called = True
        event_stamp(v.order, f"callback_called:{tool_name}")
        # Explicitly never pass updated_permissions -- this is the behavior
        # AutoCode's real adapter must also follow (see 0.10a).
        return PermissionResultAllow(updated_input=input_data)

    options = ClaudeAgentOptions(
        cli_path=cli_path,
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(hooks=[pre_tool_use_hook])]},
        permission_mode="default",
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(
                "Run these two exact shell commands using the Bash tool, as two separate "
                f"tool calls, in this order: first `{cmd1}`, then `{cmd2}`."
            )
            async for _m in client.receive_response():
                pass
        v.process_outcome = "completed"
    except Exception as e:  # noqa: BLE001
        v.sdk_exception = f"{type(e).__name__}: {e}"
        v.process_outcome = "crashed"

    exec1 = execution_count(canary1, token1)
    exec2 = execution_count(canary2, token2)
    v.execution_count_observed = exec1 + exec2
    v.notes = (
        f"PASS if hook_calls==2 and callback_calls==2 (i.e. call #2 was independently "
        f"routed, not auto-approved from call #1's precedent) and exec1={exec1}==1, exec2={exec2}==1."
    )
    return v


if __name__ == "__main__":
    require_api_key()
    log("0.10b starting")
    verdict = asyncio.run(main())
    log(f"hook_calls={verdict.hook_calls} callback_calls={verdict.callback_calls} "
        f"execution_count={verdict.execution_count_observed}")
    verdict.emit()
