"""Focus-aware status-bar hint strings."""

from typing import Literal

from ytmusic_tui.tui.modes import ModeId

FocusKind = Literal["input", "list"]

_SEARCH_INPUT_HINTS = "enter search   esc blur   down/up complete   ? help"

_MODE_HINTS: dict[ModeId, str] = {
    "search": "enter play   a queue   A playlist   j/k g/G   / search   ? help",
    "queue": (
        "enter play   d remove   j/k g/G   o open   n save   "
        "w write   A playlist   ? help"
    ),
    "playlists": (
        "enter play   ←/→/h/l pane   j/k g/G   n new   d delete   A add   ? help"
    ),
    "profiles": "enter select   j/k g/G   n new   d delete   ? help",
    "settings": "j/k g/G field   ←/→/h/l adjust   s save   ? help",
}


def hints_for(mode_id: ModeId, focus_kind: FocusKind) -> str:
    if mode_id == "search" and focus_kind == "input":
        return _SEARCH_INPUT_HINTS
    return _MODE_HINTS[mode_id]
