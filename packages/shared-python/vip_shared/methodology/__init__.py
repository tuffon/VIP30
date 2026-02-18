from .models import DataProvenance, GranularityLevel, MethodologyResult

__all__ = [
    "MethodologyAnalyzer",
    "MethodologyResult",
    "DataProvenance",
    "GranularityLevel",
]


def __getattr__(name: str):
    if name == "MethodologyAnalyzer":
        from .analyzer import MethodologyAnalyzer

        return MethodologyAnalyzer
    raise AttributeError(name)
