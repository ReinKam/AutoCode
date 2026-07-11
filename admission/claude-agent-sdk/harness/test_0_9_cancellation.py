"""
Gate 0 / Test 0.9 — cancellation while can_use_tool is pending (mechanical
variant, per the agreed spec: block the callback on an asyncio.Event, cancel
the query task, then check the side effect).

Still requires a live, authenticated session: can_use_tool only ever fires
inside a real query() where Claude has actually requested a tool call. This
harness cannot fake that half without testing our own mock instead of the
SDK, which was explicitly ruled out for this admission process.

Pass criteria:
  - execution_count == 0 after cancellation
  - the callback was in fact still pending (never got to return) at the
    moment of cancellation, confirmed via callback_returned flag
  - no exception is silently swallowed such that a later, unrelated call
    could be mistaken for an approval of this one (checked by asserting
    callback_calls == 1, not >1, after cancellation + a short grace period)
"""
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk.types import PermissionResultAllow

sys.path.insert(0, str(Path(__file__).parent))
from common import Verdict, canary_bash_command, event_stamp, execution_count, log, new_canary_token, require_api_key, require_cli_pinned  # noqa: E402

TEST_ID = "0.9"


async def main() -> Verdict:
    v = Verdict(test_id=TEST_ID, description="cancellation mid-HIL-wait -> zero execution, no false approval")
    cli_path = require_cli_pinned()
    token, canary_path = new_canary_token()
    cmd = canary_bash_command(token, canary_path)

    callback_entered = asyncio.Event()
    release_callback = asyncio.Event()  # deliberately never set -> models an
                                         # unresolved human decision
    callback_returned = False

    async def pre_tool_use_hook(input_data, tool_use_id, context):
        v.hook_calls += 1
        v.hook_called = True
        event_stamp(v.order, "hook_called")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}

    async def can_use_tool(tool_name, input_data, context):
        nonlocal callback_returned
        v.callback_calls += 1
        v.callback_called = True
        event_stamp(v.order, "callback_called_now_blocking_on_human")
        callback_entered.set()
        await release_callback.wait()  # never released in this test
        callback_returned = True  # should never execute
        return PermissionResultAllow(updated_input=input_data)

    options = ClaudeAgentOptions(
        cli_path=cli_path,
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(hooks=[pre_tool_use_hook])]},
        permission_mode="default",
    )

    async def run_session():
        async with ClaudeSDKClient(options=options) as client:
            await client.query(f"Run this exact shell command using the Bash tool, nothing else: {cmd}")
            async for _m in client.receive_response():
                pass

    task = asyncio.create_task(run_session())
    try:
        await asyncio.wait_for(callback_entered.wait(), timeout=60)
        event_stamp(v.order, "confirmed_callback_pending_now_cancelling")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            v.process_outcome = "cancelled"
        # Grace period to catch any delayed/false completion.
        await asyncio.sleep(2)
    except asyncio.TimeoutError:
        v.sdk_exception = "callback never entered within 60s -- cannot test cancellation mid-wait"
        v.process_outcome = "crashed"
        task.cancel()

    v.execution_count_observed = execution_count(canary_path, token)
    v.notes = (
        f"HARD REQUIREMENT: execution_count_observed==0, callback_returned=={callback_returned} "
        f"(must be False), callback_calls should remain 1 (no phantom re-invocation)."
    )
    return v


if __name__ == "__main__":
    require_api_key()
    log("0.9 starting")
    verdict = asyncio.run(main())
    log(f"callback_calls={verdict.callback_calls} execution_count={verdict.execution_count_observed} "
        f"process_outcome={verdict.process_outcome}")
    verdict.emit()
