"""src – top-level Python package for VIP30.

Ensure submodules used by background workers are importable via attribute
access (e.g., `src.tasks`) for RQ's import resolver.
"""

# Expose `tasks` so RQ can resolve "src.tasks.run_bid_comp_keys"
from . import tasks  # noqa: F401