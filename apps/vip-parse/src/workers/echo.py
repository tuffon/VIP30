"""Simple echo worker used as a *default* placeholder.

The function signature intentionally matches what the orchestrator expects so
that it can be swapped out without touching the runner:

    payload            – Arbitrary JSON coming from the Task Master.
    dependency_outputs – Dict with the *direct* predecessors’ outputs.

Both *sync* and *async* workers are supported by the orchestrator.  We go for
an *async* implementation here purely as an example.
"""
from __future__ import annotations

from typing import Any, Mapping


async def run(*, payload: Mapping[str, Any], dependency_outputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return the *payload* back untouched together with the *dependency_outputs*.

    Real workers would do *something* useful here – data transformation, file
    IO, calls to external services, …
    """

    return {
        "echo": payload,
        "deps": dependency_outputs or {},
    } 