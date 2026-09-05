"""Search mode: query YouTube and play or queue results."""

from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING, ClassVar, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Label, ListView

from ytmusic_cli.consts import DEFAULT_SEARCH_LIMIT
from ytmusic_cli.exceptions import YTMusicError
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Song
from ytmusic_cli.tui.widgets.song_table import SongRow, SongTable

if TYPE_CHECKING:
    from ytmusic_cli.main import YTMusicApp

_IDLE_STATUS = "Type a query and press Enter."


class SearchMode(Vertical):
    """Default landing mode."""

    class PlayingChanged(Message):
        def __init__(self, song: Song | None) -> None:
            super().__init__()
            self.song = song

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "blur_search", "Blur", show=False),
    ]

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._state = AppState()
        self._unsub_song: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="Search YouTube Music…",
            id="search_input",
        )
        yield Label(_IDLE_STATUS, id="search_status")
        yield SongTable(id="results_table")

    def on_mount(self) -> None:
        self._unsub_song = self._state.current_song.subscribe(self._on_song)
        self._set_table_visible(False)
        self.query_one("#search_input", Input).focus()

    def on_unmount(self) -> None:
        if self._unsub_song is not None:
            self._unsub_song()
            self._unsub_song = None

    def focus_query(self) -> None:
        self.query_one("#search_input", Input).focus()

    def activate(self) -> None:
        table = self.query_one("#results_table", SongTable)
        if table.display and table.has_songs():
            table.focus_list()
            return
        self.focus_query()

    def action_blur_search(self) -> None:
        self.query_one("#results_table", SongTable).focus_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search_input":
            return
        query = event.value.strip()
        if not query:
            self.app.notify("Please enter a search query", severity="warning")
            return
        self._begin_search(query)
        self._run_search(query)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, SongRow):
            return
        app = cast("YTMusicApp", self.app)
        app.play_song(event.item.song)

    @work(thread=True, exclusive=True, group="search")
    def _run_search(self, query: str) -> None:
        app = cast("YTMusicApp", self.app)
        service = app.search_service
        limit = DEFAULT_SEARCH_LIMIT
        user = self._state.current_user.get()
        if user is not None:
            limit = user["search_limit"]
        try:
            results = service.search(query, max_results=limit)
        except YTMusicError as err:
            app.call_from_thread(self._on_search_error, str(err) or "Search failed")
            return
        app.call_from_thread(self._on_search_success, query, results)

    def _begin_search(self, query: str) -> None:
        self._set_status(f"Searching “{query}”…")
        self._set_table_visible(False)

    def _on_search_success(self, query: str, results: list[Song]) -> None:
        table = self.query_one("#results_table", SongTable)
        song = self._state.current_song.get()
        table.set_playing_id(song["video_id"] if song is not None else None)
        table.set_songs(results)
        if results:
            self._set_status(f"{len(results)} results for “{query}”")
            self._set_table_visible(True)
            table.focus_list()
            return
        self._set_status(f"No results for “{query}”.")
        self._set_table_visible(False)
        self.notify("No results", severity="information")

    def _on_search_error(self, message: str) -> None:
        table = self.query_one("#results_table", SongTable)
        self._set_status("Search failed.")
        self._set_table_visible(table.has_songs())
        self.notify(message, severity="error")

    def _on_song(self, song: Song | None) -> None:
        if self.is_mounted:
            self.post_message(self.PlayingChanged(song))

    def on_search_mode_playing_changed(self, message: PlayingChanged) -> None:
        table = self.query_one("#results_table", SongTable)
        song = message.song
        table.set_playing_id(song["video_id"] if song is not None else None)

    def _set_status(self, text: str) -> None:
        self.query_one("#search_status", Label).update(text)

    def _set_table_visible(self, visible: bool) -> None:
        self.query_one("#results_table", SongTable).display = visible
