"""Backwards-compatible import for the Xactimate rough draft parser."""

try:
    # When accessed as part of the ``parse`` package (e.g. ``python -m parse.parse_dir``)
    # the relative import succeeds.
    from .xactimate import XactimateRoughDraftParser
except ImportError:  # pragma: no cover - exercised when run as a script
    # ``python parse/parse_dir.py`` loads modules without package context, so we
    # fall back to an absolute import where ``parse`` is the sys.path entry.
    from xactimate import XactimateRoughDraftParser

__all__ = ['XactimateRoughDraftParser']
