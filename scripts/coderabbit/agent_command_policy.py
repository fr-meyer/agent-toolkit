"""Policy checks for caller-provided CodeRabbit agent commands."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


# Keep the entrypoint narrow: the selected coding agent may receive arguments,
# but arbitrary shells/interpreters/scripts must not be supplied through repo vars.
ALLOWED_AGENT_EXECUTABLES = frozenset({"agent", "cursor-agent"})


def validate_agent_command(command: Sequence[str]) -> str | None:
    """Return a policy error for an untrusted command, or None when allowed."""
    if not command:
        return None

    executable = Path(command[0]).name
    if executable not in ALLOWED_AGENT_EXECUTABLES:
        allowed = ", ".join(sorted(ALLOWED_AGENT_EXECUTABLES))
        return (
            f"Agent command executable '{command[0]}' is not allowlisted; "
            f"the first executable must be one of: {allowed}."
        )
    return None
