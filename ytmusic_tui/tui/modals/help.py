"""Help overlay listing the player keymap."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ytmusic_tui.tui.widgets.list_motion import motion_step

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
<  z         Previous / next (ISO)
z  x         Previous / next (US)
             Settings picks which pair is active
e  r         Seek -5s / +5s
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
j  k         Move in lists / scroll help
g            First item / help top
G            Last item / help bottom
Ctrl+d  u    Half-page down / up
Ctrl+f  b    Page down / up
i            Focus search from a song list
h  l         Playlist pane or setting value
"""


class HelpScroll(VerticalScroll):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "scroll_down", show=False),
        Binding("k", "scroll_up", show=False),
        Binding("g", "scroll_home", show=False),
        Binding("G", "scroll_end", show=False),
        Binding("ctrl+d", "half_page_down", show=False),
        Binding("ctrl+u", "half_page_up", show=False),
        Binding("ctrl+f", "page_down", show=False),
        Binding("ctrl+b", "page_up", show=False),
    ]

    def action_half_page_down(self) -> None:
        self.scroll_relative(
            y=motion_step(self.scrollable_content_region.height, half=True),
            animate=False,
        )

    def action_half_page_up(self) -> None:
        self.scroll_relative(
            y=-motion_step(self.scrollable_content_region.height, half=True),
            animate=False,
        )


class HelpModal(ModalScreen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with HelpScroll(id="help_panel"):
            yield Static(_HELP_TEXT)

    def on_mount(self) -> None:
        self.query_one("#help_panel", HelpScroll).focus()
