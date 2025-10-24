"""Text corruption heuristics for PDF preflight."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List

_DUPLICATE_RUN_RE = re.compile(r"([A-Za-z])\1+")
_BRACKET_DIGIT_RE = re.compile(r"[\[\]{}()0-9]")


@dataclass
class LineMetrics:
    """Computed metrics for a single line of text."""

    line: str
    duplicate_run_ratio: float
    alpha_digit_ratio: float
    readability_scores: Dict[str, float]


@dataclass
class LineAnalysis:
    """Result of running the corruption checks on a line."""

    metrics: LineMetrics
    flags: List[str]


def _readability_score(text: str) -> float:
    tokens = [tok for tok in re.split(r"\s+", text.strip()) if tok]
    if not tokens:
        return 0.0

    token_scores: List[float] = []
    for token in tokens:
        length = len(token)
        if length == 0:
            continue
        alpha_count = sum(1 for ch in token if ch.isalpha())
        token_scores.append(alpha_count / length)

    if not token_scores:
        return 0.0

    return sum(token_scores) / len(token_scores)


def _duplicate_run_ratio(line: str) -> float:
    matches = list(_DUPLICATE_RUN_RE.finditer(line))
    if not matches:
        return 0.0

    duplicated = sum(len(match.group(0)) - 1 for match in matches)
    total = max(len(line.strip()), 1)
    return duplicated / total


def _alpha_digit_ratio(line: str) -> float:
    tokens = [tok for tok in re.split(r"\s+", line) if tok]
    if not tokens:
        return 0.0

    burst_lengths: List[int] = []
    for token in tokens:
        if any(ch.isalpha() for ch in token) and _BRACKET_DIGIT_RE.search(token):
            burst_lengths.append(len(token))

    if not burst_lengths:
        return 0.0

    total_length = sum(len(tok) for tok in tokens)
    if total_length == 0:
        return 0.0

    return sum(burst_lengths) / total_length


def analyse_line(line: str) -> LineAnalysis:
    """Run heuristic checks against a line of PDF text."""

    duplicate_ratio = _duplicate_run_ratio(line)
    alpha_digit_ratio = _alpha_digit_ratio(line)
    base_score = _readability_score(line)
    even_score = _readability_score(line[::2]) if len(line) > 2 else 0.0
    odd_score = _readability_score(line[1::2]) if len(line) > 2 else 0.0

    metrics = LineMetrics(
        line=line,
        duplicate_run_ratio=duplicate_ratio,
        alpha_digit_ratio=alpha_digit_ratio,
        readability_scores={
            "base": base_score,
            "even": even_score,
            "odd": odd_score,
        },
    )

    flags: List[str] = []
    if duplicate_ratio >= 0.12:
        flags.append("duplicate_char_runs")
    if alpha_digit_ratio >= 0.5:
        flags.append("alphanumeric_bursts")

    best_alt = max(even_score, odd_score)
    if best_alt - base_score >= 0.25 and best_alt >= 0.55:
        flags.append("interleaved_characters")

    return LineAnalysis(metrics=metrics, flags=flags)


def score_page_lines(lines: Iterable[str], sample_limit: int) -> List[LineAnalysis]:
    """Analyse up to ``sample_limit`` lines from ``lines``."""

    analysed: List[LineAnalysis] = []
    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue
        analysed.append(analyse_line(clean_line[:512]))
        if len(analysed) >= sample_limit:
            break
    return analysed
