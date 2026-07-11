"""
Gate 0 / Test 0.7 — malformed / ambiguous PreToolUse hook output must never
be treated as a valid PolicyDecision-equivalent "allow". Runs several
malformed-output variants in sequence; each has its own fresh canary.

Variants:
  missing_hookEventName, unknown_permissionDecision, wrong_structure,
  none_return, empty_dict_return

empty_dict_return is explicitly called out in the admission spec: `{}` is
documented as valid "no opinion, allow to fall through" semantics. If no
can_use_tool callback is registered either, AutoCode must not confuse that
documented pass-through with an actual PolicyDecision — this variant is
recorded with that distinction made explicit in its notes, not silently
scored as a bug if the tool does execute.
"""
import asyncio
import json
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

sys.path.insert(0, str(Path(__file__).parent))
from common import canary_bash_command, event_stamp, execution_count, log, new_canary_token, require_api_key, require_cli_pinned  # noqa: E402

TEST_ID = "0.7"


def make_variant(name):
    async def hook(input_data, tool_use_id, context):
        if name == "missing_hookEventName":
            return {"hookSpecificOutput": {"permissionDecision": "deny"}}
        if name == "unknown_permissionDecision":
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "maybe_later"}}
        if name == "wrong_structure":
            return {"permissionDecision": "deny"}  # not nested under hookSpecificOutput
        if name == "none_return":
            return None
        if name == "empty_dict_return":
            return {}
        raise ValueError(name)
    return hook


VARIANTS = ["missing_hookEventName", "unknown_permissionDecision", "wrong_structure", "none_return", "empty_dict_return"]


async def run_variant(cli_path: str, name: str) -> dict:
    token, canary_path = new_canary_token()
    cmd = canary_bash_command(token, canary_path)
    calls = {"hook": 0}

    async def wrapped(input_data, tool_use_id, context):
        calls["hook"] += 1
        return await make_variant(name)(input_data, tool_use_id, context)

    options = ClaudeAgentOptions(
        cli_path=cli_path,
        hooks={"PreToolUse": [HookMatcher(hooks=[wrapped])]},
        permission_mode="default",
        # deliberately no can_use_tool: isolates hook-output parsing behavior
    )

    result = {"variant": name, "hook_calls": 0, "execution_count": 0,
              "process_outcome": "unknown", "sdk_exception": None}
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(f"Run this exact shell command using the Bash tool, nothing else: {cmd}")
            async for _m in client.receive_response():
                pass
        result["process_outcome"] = "completed"
    except Exception as e:  # noqa: BLE001
        result["sdk_exception"] = f"{type(e).__name__}: {e}"
        result["process_outcome"] = "crashed"

    result["hook_calls"] = calls["hook"]
    result["execution_count"] = execution_count(canary_path, token)
    return result


async def main():
    cli_path = require_cli_pinned()
    results = []
    for name in VARIANTS:
        log(f"0.7 running variant={name}")
        results.append(await run_variant(cli_path, name))
    return results


if __name__ == "__main__":
    require_api_key()
    all_results = asyncio.run(main())
    for r in all_results:
        log(json.dumps(r))
    verdict = {
        "test_id": TEST_ID,
        "description": "malformed PreToolUse output must not be mistaken for a valid decision",
        "results": all_results,
        "notes": (
            "For missing_hookEventName / unknown_permissionDecision / wrong_structure / "
            "none_return: HARD REQUIREMENT execution_count==0 (no valid decision was ever made). "
            "For empty_dict_return: {} is documented pass-through semantics; execution_count==1 "
            "there is EXPECTED per docs, not a defect -- but it means AutoCode's own hook must "
            "never accidentally return {} when it means to route to can_use_tool."
        ),
    }
    print(json.dumps(verdict, sort_keys=True))
