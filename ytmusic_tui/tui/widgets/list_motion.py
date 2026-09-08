"""Shared vim list-motion bindings for ListView and OptionList subclasses."""

from textual.binding import Binding, BindingType

LIST_MOTION_BINDINGS: tuple[BindingType, ...] = (
    Binding("j", "cursor_down", show=False),
    Binding("k", "cursor_up", show=False),
    Binding("g", "first", show=False),
    Binding("G", "last", show=False),
    Binding("ctrl+d", "half_page_down", show=False),
    Binding("ctrl+u", "half_page_up", show=False),
    Binding("ctrl+f", "page_down", show=False),
    Binding("ctrl+b", "page_up", show=False),
    Binding("pagedown", "page_down", show=False),
    Binding("pageup", "page_up", show=False),
)


def motion_step(height: int, *, half: bool) -> int:
    if height <= 0:
        return 1
    if half:
        return max(1, height // 2)
    return max(1, height)


def clamp_cursor(current: int | None, delta: int, count: int) -> int | None:
    if count <= 0:
        return None
    base = current if current is not None else 0
    return max(0, min(base + delta, count - 1))
