"""Persistent player chrome: modes, now-playing, and status."""

from typing import Protocol, runtime_checkable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, ListView

from ytmusic_cli.consts import COMPACT_HEIGHT_ROWS, WIDE_LAYOUT_COLUMNS
from ytmusic_cli.music.state import AppState
from ytmusic_cli.tui.app import ytmusic_app
from ytmusic_cli.tui.modes.playlists import PlaylistsMode
from ytmusic_cli.tui.modes.profiles import ProfilesMode
from ytmusic_cli.tui.modes.queue import QueueMode
from ytmusic_cli.tui.modes.search import SearchMode
from ytmusic_cli.tui.modes.settings import SettingsMode
from ytmusic_cli.tui.widgets.mode_bar import ModeBar
from ytmusic_cli.tui.widgets.now_playing import NowPlaying
from ytmusic_cli.tui.widgets.queue_list import QueueList
from ytmusic_cli.tui.widgets.song_table import SongRow, SongTable
from ytmusic_cli.tui.widgets.status_bar import StatusBar

MODES: tuple[str, ...] = (
    "search",
    "queue",
    "playlists",
    "profiles",
    "settings",
)

HINTS: dict[str, str] = {
    "search": (
        "enter play   space pause   down/up complete   a queue   "
        "A playlist   j/k move   / search   ? help"
    ),
    "queue": (
        "enter play   d remove   j/k move   o open   n save   "
        "w write   A playlist   ? help"
    ),
    "playlists": "enter play   ←/→/h/l pane   n new   d delete   A add   ? help",
    "profiles": "enter select   n new   d delete   ? help",
    "settings": "j/k field   ←/→/h/l adjust   s save   ? help",
}


@runtime_checkable
class AppMode(Protocol):
    def activate(self) -> None: ...

    def reload(self) -> None: ...


class AppShell(Vertical):
    """Single-screen player layout."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.current_mode = "search"

    def compose(self) -> ComposeResult:
        yield ModeBar(id="mode_bar")
        with Horizontal(id="body_row"):
            with Vertical(id="main_column"):
                yield SearchMode(id="search")
                yield QueueMode(id="queue")
                yield PlaylistsMode(id="playlists")
                yield ProfilesMode(id="profiles")
                yield SettingsMode(id="settings")
            with Vertical(id="queue_pane"):
                yield Label("Queue")
                yield QueueList(id="side_queue")
        with Vertical(id="chrome"):
            yield NowPlaying(id="now_playing")
            yield StatusBar(id="status_bar")

    def on_mount(self) -> None:
        self.switch_mode("search")
        self._apply_compact_chrome()
        self.query_one(SearchMode).focus_query()

    def on_resize(self) -> None:
        self._apply_wide_layout()
        self._apply_compact_chrome()

    def switch_mode(self, mode_id: str) -> None:
        if mode_id not in MODES:
            return
        self.current_mode = mode_id
        for item in MODES:
            self.query_one(f"#{item}", Widget).display = item == mode_id
        self.query_one("#mode_bar", ModeBar).set_active(mode_id)
        self.query_one("#status_bar", StatusBar).set_hints(HINTS[mode_id])
        self._apply_wide_layout()
        widget = self.query_one(f"#{mode_id}", Widget)
        if isinstance(widget, AppMode):
            widget.reload()
            widget.activate()

    def next_mode(self) -> None:
        index = MODES.index(self.current_mode)
        self.switch_mode(MODES[(index + 1) % len(MODES)])

    def previous_mode(self) -> None:
        index = MODES.index(self.current_mode)
        self.switch_mode(MODES[(index - 1) % len(MODES)])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, SongRow):
            return
        table = next(
            (
                node
                for node in event.item.ancestors_with_self
                if isinstance(node, QueueList)
            ),
            None,
        )
        if table is None:
            return
        app = ytmusic_app(self.app)
        index = table.selected_index()
        if index is not None:
            app.play_playlist(list(AppState().queue.get()), index)
        event.stop()

    def reload_playlists_if_visible(self) -> None:
        mode = self.query_one(PlaylistsMode)
        if mode.display:
            mode.reload()

    def on_song_table_delete_requested(
        self,
        message: SongTable.DeleteRequested,
    ) -> None:
        if not isinstance(message.table, QueueList):
            return
        app = ytmusic_app(self.app)
        app.remove_from_queue(message.index)
        message.stop()

    def _apply_wide_layout(self) -> None:
        pane = self.query_one("#queue_pane", Vertical)
        wide = self.size.width >= WIDE_LAYOUT_COLUMNS
        show = wide and self.current_mode != "queue"
        pane.set_class(show, "-visible")
        pane.display = show

    def _apply_compact_chrome(self) -> None:
        compact = self.size.height < COMPACT_HEIGHT_ROWS
        self.query_one("#chrome", Vertical).set_class(compact, "-compact")
