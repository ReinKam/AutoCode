"""
Gate 0 / Test 0.4 — does a PreToolUse hook actually close the auto-approval
gap described in the docs (bare allowed_tools, acceptEdits, bypassPermissions,
a settings.json allow rule)?

For each of the four permission configurations, run twice:
  (a) WITHOUT any hook  -> expect can_use_tool to be SKIPPED (per docs)
  (b) WITH the AutoCode-style PreToolUse hook forcing "ask" -> expect
      can_use_tool to be CALLED regardless of the auto-approval config

Pass criteria: in every "WITH hook" run, hook_calls >= 1 and callback_calls
>= 1. The "WITHOUT hook" runs are recorded for contrast, not as a pass/fail
gate (a callback skip there is the documented, expected behavior).
"""
import asyncio
import json
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk.types import PermissionResultAllow

sys.path.insert(0, str(Path(__file__).parent))
from common import canary_bash_command, event_stamp, execution_count, log, new_canary_token, require_api_key, require_cli_pinned  # noqa: E402

TEST_ID = "0.4"

CONFIGS = [
    {"name": "bare_allowed_tools", "kwargs": {"allowed_tools": ["Bash"]}},
    {"name": "accept_edits_mode", "kwargs": {"permission_mode": "acceptEdits"}},
    {"name": "bypass_permissions_mode", "kwargs": {"permission_mode": "bypassPermissions"}},
    # A settings.json allow rule is intentionally not simulated here — it
    # requires a project settings file and setting_sources=["project"];
    # left as a manual variant if the first three already prove the hook
    # closes the gap for the mechanisms available directly via options.
]


async def run_once(cli_path: str, cfg: dict, with_hook: bool) -> dict:
    result = {"config": cfg["name"], "with_hook": with_hook,
              "hook_calls": 0, "callback_calls": 0, "execution_count": 0,
              "process_outcome": "unknown", "sdk_exception": None}
    token, canary_path = new_canary_token()
    cmd = canary_bash_command(token, canary_path)

    async def pre_tool_use_hook(input_data, tool_use_id, context):
        result["hook_calls"] += 1
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}

    async def can_use_tool(tool_name, input_data, context):
        result["callback_calls"] += 1
        return PermissionResultAllow(updated_input=input_data)

    kwargs = dict(cfg["kwargs"])
    kwargs["cli_path"] = cli_path
    kwargs["can_use_tool"] = can_use_tool
    if with_hook:
        kwargs["hooks"] = {"PreToolUse": [HookMatcher(hooks=[pre_tool_use_hook])]}

    options = ClaudeAgentOptions(**kwargs)
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(f"Run this exact shell command using the Bash tool, nothing else: {cmd}")
            async for _m in client.receive_response():
                pass
        result["process_outcome"] = "completed"
    except Exception as e:  # noqa: BLE001
        result["sdk_exception"] = f"{type(e).__name__}: {e}"
        result["process_outcome"] = "crashed"

    result["execution_count"] = execution_count(canary_path, token)
    return result


async def main() -> list[dict]:
    cli_path = require_cli_pinned()
    results = []
    for cfg in CONFIGS:
        for with_hook in (False, True):
            log(f"0.4 running config={cfg['name']} with_hook={with_hook}")
            r = await run_once(cli_path, cfg, with_hook)
            results.append(r)
    return results


if __name__ == "__main__":
    require_api_key()
    all_results = asyncio.run(main())
    for r in all_results:
        log(json.dumps(r))
    verdict = {
        "test_id": TEST_ID,
        "description": "auto-approval paths must still hit the hook when the hook is present",
        "results": all_results,
        "notes": (
            "PASS if every with_hook=true row has hook_calls>=1 and callback_calls>=1, "
            "regardless of config. with_hook=false rows are contrast data, not gate criteria."
        ),
    }
    print(json.dumps(verdict, sort_keys=True))
