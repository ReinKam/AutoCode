"""
Gate 0 / Test 0.1 — permissionDecision: "ask" reliably reaches can_use_tool.

Setup:
  - PreToolUse hook (no matcher -> fires for every tool) always returns
    {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}
  - can_use_tool records that it was called and DENIES (so no real side
    effect should occur here; execution proof belongs to 0.2/0.3).
  - default permission_mode, no allow/deny rules, so nothing upstream of
    the hook could resolve the call on its own.

Pass criteria (per Admission Gate 0 spec):
  hook called exactly once
  can_use_tool called exactly once
  no execution before the callback responded
"""

import asyncio
import sys

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk.types import PermissionResultDeny

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import (  # noqa: E402
    Verdict,
    canary_bash_command,
    event_stamp,
    execution_count,
    log,
    new_canary_token,
    require_api_key,
    require_cli_pinned,
)

TEST_ID = "0.1"


async def main() -> Verdict:
    v = Verdict(test_id=TEST_ID, description='PreToolUse "ask" routes to can_use_tool')
    cli_path = require_cli_pinned()
    token, canary_path = new_canary_token()
    cmd = canary_bash_command(token, canary_path)

    async def pre_tool_use_hook(input_data, tool_use_id, context):
        v.hook_calls += 1
        v.hook_called = True
        event_stamp(v.order, f"hook_called:{input_data.get('tool_name')}")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
            }
        }

    async def can_use_tool(tool_name, input_data, context):
        v.callback_calls += 1
        v.callback_called = True
        event_stamp(v.order, f"callback_called:{tool_name}")
        # Deny here: this test is only about routing, not execution.
        return PermissionResultDeny(message="0.1: routing test, denying by design")

    options = ClaudeAgentOptions(
        cli_path=cli_path,
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(hooks=[pre_tool_use_hook])]},
        permission_mode="default",
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(
                f"Run this exact shell command using the Bash tool, nothing else: {cmd}"
            )
            async for _message in client.receive_response():
                pass
        v.process_outcome = "completed"
    except Exception as e:  # noqa: BLE001
        v.sdk_exception = f"{type(e).__name__}: {e}"
        v.process_outcome = "crashed"

    v.execution_count_observed = execution_count(canary_path, token)
    return v


if __name__ == "__main__":
    require_api_key()
    log(f"0.1 starting, canary dir = {__import__('pathlib').Path(__file__).parent / '_canary'}")
    verdict = asyncio.run(main())
    log(f"hook_calls={verdict.hook_calls} callback_calls={verdict.callback_calls} "
        f"execution_count={verdict.execution_count_observed}")
    verdict.notes = (
        "PASS if hook_calls==1 and callback_calls==1 and execution_count_observed==0"
    )
    verdict.emit()
