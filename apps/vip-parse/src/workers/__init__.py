"""Dynamic workers namespace.

All modules in this package are *discovered at runtime* by the
:pyclass:`~src.orchestrator.runners.TaskDispatcher`.  Nothing in here is
required for basic functionality but exposing the *default* `echo` worker at
package level makes interactive exploration slightly nicer::

    from src.workers import echo
    await echo.run(payload={...})
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__: list[str] = [
    "echo",
]

# Lazily import the *default* echo worker so that it only incurs overhead when
# actually accessed.

def __getattr__(name: str) -> Any:  # noqa: D401
    if name == "echo":
        return import_module("src.workers.echo")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}") 