"""Help overlay listing the player keymap."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

_HELP_TEXT = """\
YTMusic - keyboard

Anyone
1-5          Switch mode
Tab          Next mode
Shift+Tab    Previous mode
Arrows       Move in lists / adjust settings
Enter        Play now
a            Append to queue
A            Add to playlist
Space        Play / pause
/            Search and focus query
+  =  -      Volume
>  <         Next / previous in queue
Down Up      Complete suggestion
d            Remove queue item, playlist, track, or profile
n            New playlist, profile, or save queue
o            Open playlist into queue
w            Write queue over working playlist
s            Save settings
?            Help
Esc          Blur search / close dialog
q            Quit (or close this help)
Ctrl+q       Quit

Vim
Shift+H      Previous mode
Shift+L      Next mode
j  k         Move in lists
g            First item
G            Last item
Ctrl+d  u    Half-page down / up
Ctrl+f  b    Page down / up
i            Focus search from a song list
h  l         Playlist pane or setting value
"""


class HelpModal(ModalScreen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help_panel"):
            yield Static(_HELP_TEXT)
