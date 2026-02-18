from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from vip_parser.xactimate.visible_text import (
    VisibleTextConfig,
    extract_visible_lines,
    filter_visible_chars,
    is_visible_char,
    normalize_color,
)


def _char(
    text: str,
    *,
    color: Any = (0, 0, 0),
    size: float = 8.0,
    render_mode: int = 0,
    x0: float | None = None,
    x1: float | None = None,
    top: float | None = None,
    bottom: float | None = None,
) -> Dict[str, Any]:
    data = {
        "text": text,
        "non_stroking_color": color,
        "size": size,
        "text_rendering_mode": render_mode,
        "object_type": "char",
    }
    if x0 is not None:
        data["x0"] = x0
    if x1 is not None:
        data["x1"] = x1
    if top is not None:
        data["top"] = top
    if bottom is not None:
        data["bottom"] = bottom
    return data


def test_is_visible_char_filters_white_on_white():
    cfg = VisibleTextConfig()
    invisible = _char("x", color=(1, 1, 1))
    assert is_visible_char(invisible, cfg) is False


def test_is_visible_char_filters_invisible_render_mode():
    cfg = VisibleTextConfig()
    char = _char("x", render_mode=3)
    assert is_visible_char(char, cfg) is False


def test_is_visible_char_enforces_min_font_size():
    cfg = VisibleTextConfig(min_font_size=3.0)
    char = _char("x", size=1.0)
    assert is_visible_char(char, cfg) is False


def test_filter_visible_chars_keeps_only_dark_text():
    cfg = VisibleTextConfig()
    chars = [
        _char("T"),
        _char("X", color=(0.99, 0.99, 0.99)),
        _char("B", color=(0.2, 0.2, 0.2)),
    ]
    filtered = filter_visible_chars(DummyPage(chars), cfg)
    assert [c["text"] for c in filtered] == ["T", "B"]


def test_filter_visible_chars_drops_out_of_bounds():
    cfg = VisibleTextConfig()
    chars = [
        {**_char("A"), "x0": 10.0, "x1": 12.0, "top": 10.0, "bottom": 12.0},
        {**_char("B"), "x0": -50.0, "x1": -48.0, "top": 10.0, "bottom": 12.0},
    ]
    filtered = filter_visible_chars(DummyPage(chars), cfg)
    assert [c["text"] for c in filtered] == ["A"]


def test_normalize_color_handles_scalar_and_tuple():
    assert normalize_color(0.5) == (0.5, 0.5, 0.5)
    assert normalize_color(255) == (1.0, 1.0, 1.0)
    assert normalize_color((0.1, 0.2, 0.3, 0.4)) == (0.1, 0.2, 0.3)


@dataclass
class DummyPage:
    chars: List[Dict[str, Any]]
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 600.0, 800.0)

    def filter(self, fn):
        filtered = [c for c in self.chars if fn(c)]
        return DummyPage(filtered, bbox=self.bbox)

    def extract_text(self, **_kwargs):
        return "".join(c["text"] for c in self.chars)

    def extract_words(self, **_kwargs):
        text = self.extract_text()
        return [{"text": tok} for tok in text.split()]


def test_extract_visible_lines_drops_overlay_text():
    cfg = VisibleTextConfig(min_font_size=1.0)
    chars = [
        _char("Totals: "),
        _char("GueHHsaatllll wwBaayyedroom ", color=(0.99, 0.99, 0.99)),
        _char("Guest Bedroom 1.54 2,470.98"),
        _char("\n"),
    ]
    page = DummyPage(chars)
    lines = extract_visible_lines(page, config=cfg, debug_page_number=1)
    assert lines == ["Totals: Guest Bedroom 1.54 2,470.98"]


def test_filter_visible_chars_drops_small_font_duplicate_overlay():
    cfg = VisibleTextConfig()
    overlay_chars: List[Dict[str, Any]] = []
    top = 100.0
    for idx, letter in enumerate("BATH TUB"):
        if letter == " ":
            continue
        x = 5.0 * idx
        overlay_chars.append(_char(letter, size=6.0, x0=x, x1=x + 1.0, top=top, bottom=top + 2))
        overlay_chars.append(
            _char(letter, size=6.0, x0=x + 0.05, x1=x + 1.05, top=top + 0.03, bottom=top + 2.03)
        )

    table_top = 200.0
    table_chars = [
        _char(ch, size=6.0, x0=40.0 + i * 4, x1=40.5 + i * 4, top=table_top, bottom=table_top + 2)
        for i, ch in enumerate("CONTENT")
    ]
    page = DummyPage(overlay_chars + table_chars)

    filtered = filter_visible_chars(page, cfg)
    overlay_kept = [c for c in filtered if abs(c.get("top", 0) - top) < 0.1]
    assert overlay_kept == []
    table_kept = [c["text"] for c in filtered if abs(c.get("top", 0) - table_top) < 0.1]
    assert table_kept == list("CONTENT")


def test_duplicate_overlay_not_dropped_when_span_exceeds_guard():
    cfg = VisibleTextConfig(overlay_duplicate_max_x_span=80.0)
    top = 120.0
    chars: List[Dict[str, Any]] = []
    for idx, letter in enumerate("WIDE OVERLAY "):
        if letter == " ":
            continue
        x = idx * 20.0
        chars.append(_char(letter, size=7.0, x0=x, x1=x + 1.0, top=top, bottom=top + 2))
        chars.append(_char(letter, size=7.0, x0=x + 0.05, x1=x + 1.05, top=top + 0.03, bottom=top + 2.03))
    page = DummyPage(chars)
    filtered = filter_visible_chars(page, cfg)
    # All chars remain because the span (~200pt) exceeds the guard.
    assert len(filtered) == len(chars)


def test_duplicate_overlay_wide_span_drops_when_guard_disabled():
    cfg = VisibleTextConfig(overlay_duplicate_max_x_span=0.0)
    top = 125.0
    chars: List[Dict[str, Any]] = []
    for idx, letter in enumerate("HALLWAY"):
        x = idx * 40.0
        chars.append(_char(letter, size=6.0, x0=x, x1=x + 1.0, top=top, bottom=top + 2))
        chars.append(_char(letter, size=6.0, x0=x + 0.05, x1=x + 1.05, top=top + 0.03, bottom=top + 2.03))
    page = DummyPage(chars)
    filtered = filter_visible_chars(page, cfg)
    assert all(abs(c.get("top", 0) - top) > 0.1 for c in filtered)


def test_duplicate_overlay_dropped_even_with_far_micro_ticks():
    cfg = VisibleTextConfig()
    top = 130.0
    chars: List[Dict[str, Any]] = []
    for idx, letter in enumerate("HAL"):
        x = idx * 5.0
        chars.append(_char(letter, size=6.0, x0=x, x1=x + 1.0, top=top, bottom=top + 2))
        chars.append(_char(letter, size=6.0, x0=x + 0.05, x1=x + 1.05, top=top + 0.03, bottom=top + 2.03))
    # Add tiny tick far away to ensure span guard ignores it.
    chars.append(_char("'", size=1.0, x0=200.0, x1=200.2, top=top, bottom=top + 0.5))
    page = DummyPage(chars)
    filtered = filter_visible_chars(page, cfg)
    assert all(abs(c.get("top", 0) - top) > 0.1 for c in filtered)


def test_extract_visible_lines_drops_dark_overlay_not_just_white():
    cfg = VisibleTextConfig()
    lines: List[Dict[str, Any]] = []
    top = 120.0
    for idx, letter in enumerate("GARAGE "):
        if letter == " ":
            continue
        x = 10 + idx * 4
        lines.append(_char(letter, size=6.0, x0=x, x1=x + 1, top=top, bottom=top + 2))
        lines.append(_char(letter, size=6.0, x0=x + 0.04, x1=x + 1.04, top=top + 0.02, bottom=top + 2.02))

    real_top = 140.0
    for token in ["Totals:", "Master", "Closet", "Hers", "0.93", "1,076.22"]:
        x = 40.0 + len(lines)
        lines.append(
            _char(f"{token} ", size=10.0, x0=x, x1=x + len(token), top=real_top, bottom=real_top + 3)
        )
    lines.append(_char("\n", size=10.0, top=real_top + 5, bottom=real_top + 6))

    page = DummyPage(lines)
    result = extract_visible_lines(page, config=cfg)
    assert result == ["Totals: Master Closet Hers 0.93 1,076.22"]


def test_small_font_groups_with_high_oob_ratio_are_dropped():
    cfg = VisibleTextConfig()
    baseline_top = 50.0
    chars: List[Dict[str, Any]] = []
    # 8 glyphs, half out of bounds on the left
    for idx in range(8):
        x = -20.0 + idx * 5
        chars.append(_char("X", size=6.0, x0=x, x1=x + 1, top=baseline_top, bottom=baseline_top + 2))
    page = DummyPage(chars)
    filtered = filter_visible_chars(page, cfg)
    assert filtered == []


def test_measurement_overlay_is_removed():
    cfg = VisibleTextConfig()
    top = 260.0
    measurement = [
        _char(ch, size=6.0, x0=90.0 + i * 2, x1=90.5 + i * 2, top=top, bottom=top + 2)
        for i, ch in enumerate("6'2\"")
    ]
    real_top = 265.0
    real_line = [
        _char(token, size=10.0, x0=120.0 + i * 5, x1=125.0 + i * 5, top=real_top, bottom=real_top + 3)
        for i, token in enumerate(["Utility", " ", "Room", " ", "Height:", " ", "8'"])
    ]
    page = DummyPage(measurement + real_line)
    filtered = filter_visible_chars(page, cfg)
    measurement_kept = [c for c in filtered if abs(c.get("top", 0) - top) < 0.1]
    assert measurement_kept == []
    assert any(abs(c.get("top", 0) - real_top) < 0.1 for c in filtered)


def test_measurement_line_with_letters_is_preserved():
    cfg = VisibleTextConfig()
    top = 270.0
    chars = [
        _char(ch, size=10.0, x0=80.0 + i * 4, x1=81.0 + i * 4, top=top, bottom=top + 3)
        for i, ch in enumerate("Height 8'")
    ]
    page = DummyPage(chars)
    filtered = filter_visible_chars(page, cfg)
    assert [c["text"] for c in filtered] == [c["text"] for c in chars]

