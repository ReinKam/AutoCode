"""
normalize_to_action_proposal: SDK tool call -> ActionProposalSchema document.

Deliberately a strict, explicit mapping table — not a heuristic. An
unrecognized tool_name raises, rather than being guessed at. This mirrors
the rule matcher's own principle: this layer describes structure, it does
not infer intent.

Scope for this MVP wiring: file_read, file_write, file_delete, run_command.
Git operations (git_push, git_merge, branch policy) are explicitly out of
scope here and should raise, per the agreed sequencing — they carry
different consequence and deserve their own mapping + tests.
"""

import uuid
from datetime import datetime, timezone

# Maps a Claude Agent SDK tool_name to (action_type, path_field | None, is_command)
_TOOL_MAP = {
    "Read": ("file_read", "file_path", False),
    "Write": ("file_write", "file_path", False),
    "Edit": ("file_write", "file_path", False),
    "Delete": ("file_delete", "file_path", False),
    "Bash": ("run_command", None, True),
}

_OUT_OF_SCOPE_TOOLS = {"git_push", "git_merge", "GitPush", "GitMerge"}


class UnsupportedToolError(ValueError):
    pass


def normalize_to_action_proposal(tool_name: str, tool_input: dict, proposed_by: str) -> dict:
    if tool_name in _OUT_OF_SCOPE_TOOLS:
        raise UnsupportedToolError(
            f"'{tool_name}' is a git operation. Git tool mapping is explicitly out of "
            f"scope for this adapter version — it requires its own condition fields "
            f"and golden tests before being wired in."
        )

    mapping = _TOOL_MAP.get(tool_name)
    if mapping is None:
        raise UnsupportedToolError(
            f"No normalization mapping for tool_name='{tool_name}'. "
            f"Refusing to guess — add an explicit mapping entry first."
        )

    action_type, path_field, is_command = mapping

    paths = []
    payload = {}

    if path_field is not None:
        file_path = tool_input.get(path_field)
        if file_path:
            paths = [file_path]

    if is_command:
        payload = {"command": tool_input.get("command", "")}

    return {
        "action_proposal_id": str(uuid.uuid4()),
        "action_type": action_type,
        "description": f"{tool_name} tool call proposed by {proposed_by}",
        "proposed_by": proposed_by,
        "paths": paths,
        "target_branch": None,
        "payload": payload,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
