"""Backwards-compatible import for the Xactimate rough draft parser."""

if __package__:
    # When accessed as part of the ``parse`` package (e.g. ``python -m vip_parser.parse_dir``)
    # the relative import succeeds.
    from .xactimate import XactimateRoughDraftParser
else:  # pragma: no cover - exercised when run as a script
    # ``python -m vip_parser.parse_dir`` loads modules without package context, so we
    # fall back to an absolute import where ``parse`` is the sys.path entry.
    from xactimate import XactimateRoughDraftParser

__all__ = ['XactimateRoughDraftParser']
