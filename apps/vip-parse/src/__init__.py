"""src – top-level Python package for VIP30.

Ensure submodules used by background workers are importable via attribute
access (e.g., `src.tasks`) for RQ's import resolver.
"""

# Make `src.tasks` resolvable as an attribute for RQ's import logic
try:  # pragma: no cover
    from . import tasks  # noqa: F401
except Exception:
    # Defer if tasks has import-time side effects not available yet
    pass