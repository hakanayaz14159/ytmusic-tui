"""Help overlay listing the player keymap."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

_HELP_TEXT = """\
YTMusic — keyboard

1-5          Switch mode
Tab          Next mode
/            Search and focus query
Down Up      Complete suggestion
Space        Play / pause
+  -         Volume
>  <         Next / previous in queue
Enter        Play now
a            Append to queue
A            Add to playlist
d            Remove (queue or playlist track)
n            New playlist, profile, or save queue
o            Open playlist into queue
w            Write queue over working playlist
s            Save settings
Esc          Blur search / close dialog
q            Quit (or close this help)
Ctrl+q       Quit
j  k         Move in lists
?            Help
"""


class HelpModal(ModalScreen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help_panel"):
            yield Static(_HELP_TEXT)
