from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional


@dataclass
class MarkdownBlock:
    kind: str  # heading, paragraph, bullet, numbered, blank
    level: int
    text: str
    ordinal: Optional[int] = None


def parse_markdown(markdown: str) -> List[MarkdownBlock]:
    """
    Parse a small subset of Markdown (headings, ordered/bulleted lists, paragraphs).
    Returns a list of MarkdownBlock entries that downstream renderers can style.
    """
    if not isinstance(markdown, str):
        markdown = str(markdown or "")
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    blocks: List[MarkdownBlock] = []
    paragraph_buffer: List[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            paragraph_text = " ".join(line.strip() for line in paragraph_buffer if line.strip())
            if paragraph_text:
                blocks.append(MarkdownBlock(kind="paragraph", level=1, text=paragraph_text))
        paragraph_buffer.clear()

    bullet_pattern = re.compile(r"^(\s*)([-*+])\s+(.*)")
    ordered_pattern = re.compile(r"^(\s*)(\d+)\.\s+(.*)")

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.lstrip()
        if not stripped:
            flush_paragraph()
            blocks.append(MarkdownBlock(kind="blank", level=1, text=""))
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped[level:].strip() or stripped
            blocks.append(MarkdownBlock(kind="heading", level=max(1, level), text=heading_text))
            continue

        bullet_match = bullet_pattern.match(line)
        if bullet_match:
            flush_paragraph()
            indent = len(bullet_match.group(1)) // 2
            bullet_text = bullet_match.group(3).strip()
            blocks.append(MarkdownBlock(kind="bullet", level=max(1, indent + 1), text=bullet_text))
            continue

        ordered_match = ordered_pattern.match(line)
        if ordered_match:
            flush_paragraph()
            indent = len(ordered_match.group(1)) // 2
            ordinal = int(ordered_match.group(2))
            ordered_text = ordered_match.group(3).strip()
            blocks.append(
                MarkdownBlock(
                    kind="numbered",
                    level=max(1, indent + 1),
                    text=ordered_text,
                    ordinal=ordinal,
                )
            )
            continue

        paragraph_buffer.append(line)

    flush_paragraph()

    # Remove extraneous blank blocks at start/end
    while blocks and blocks[0].kind == "blank":
        blocks.pop(0)
    while blocks and blocks[-1].kind == "blank":
        blocks.pop()

    if not blocks:
        blocks.append(MarkdownBlock(kind="paragraph", level=1, text="Narrative unavailable."))

    return blocks


__all__ = ["MarkdownBlock", "parse_markdown"]


