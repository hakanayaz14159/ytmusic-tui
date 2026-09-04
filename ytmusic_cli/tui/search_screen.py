"""Search screen for querying YouTube Music and playing results."""

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, LoadingIndicator

from ytmusic_cli.music.services import PlaybackService, SearchService
from ytmusic_cli.music.types import Song


class SongListItem(ListItem):
    """List item that carries the associated Song domain object."""

    def __init__(self, song: Song) -> None:
        artist = song["artist"] or "Unknown Artist"
        super().__init__(Label(f"{song['title']} - {artist}"))
        self.song = song


class SearchScreen(Screen[None]):
    """Screen for searching tracks and triggering playback on selection."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_screen", "Back"),
    ]

    DEFAULT_CSS = """
    SearchScreen {
        layout: vertical;
    }

    SearchScreen > #search_header {
        dock: top;
        height: 3;
        padding: 0 1;
        background: #1A1A1A;
        color: #FFFFFF;
        content-align: center middle;
    }

    SearchScreen > #search_footer {
        dock: bottom;
        height: 1;
        background: #1A1A1A;
        color: #888888;
        content-align: center middle;
    }

    SearchScreen > #search_body {
        height: 1fr;
        padding: 1 2;
    }

    SearchScreen #search_input {
        margin-bottom: 1;
        border: solid #3EA6FF;
    }

    SearchScreen #search_input:focus {
        border: tall #FF0000;
    }

    SearchScreen #search_loading {
        display: none;
        height: 3;
        margin-bottom: 1;
    }

    SearchScreen #search_loading.-visible {
        display: block;
    }

    SearchScreen #results_list {
        height: 1fr;
        border: solid #222222;
        background: #1A1A1A;
    }

    SearchScreen #results_list:focus {
        border: solid #3EA6FF;
    }

    SearchScreen #results_list > ListItem.--highlight {
        background: #3EA6FF;
        color: #0F0F0F;
    }
    """

    def __init__(
        self,
        search_service: SearchService | None = None,
        playback_service: PlaybackService | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._search_service = search_service
        self._playback_service = playback_service

    @property
    def search_service(self) -> SearchService | None:
        if self._search_service is not None:
            return self._search_service
        return getattr(self.app, "search_service", None)

    @property
    def playback_service(self) -> PlaybackService | None:
        if self._playback_service is not None:
            return self._playback_service
        return getattr(self.app, "playback_service", None)

    def compose(self) -> ComposeResult:
        yield Label("Search", id="search_header")
        with Vertical(id="search_body"):
            yield Input(
                placeholder="Search YouTube Music...",
                id="search_input",
            )
            yield LoadingIndicator(id="search_loading")
            yield ListView(id="results_list")
        yield Label("[Esc] Back", id="search_footer")

    def on_mount(self) -> None:
        self.query_one("#search_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            self.notify("Please enter a search query", severity="warning")
            return
        self._set_loading(True)
        self._run_search(query)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, SongListItem):
            return
        song = item.song
        self.notify(f"Playing: {song['title']}", severity="information")
        self._play_song(song)

    def action_dismiss_screen(self) -> None:
        self.dismiss()

    @work(thread=True, exclusive=True, group="search")
    def _run_search(self, query: str) -> None:
        service = self.search_service
        if service is None:
            self.app.call_from_thread(
                self._on_search_error,
                "Search service is not available",
            )
            return
        try:
            results = service.search(query)
        except Exception as err:
            self.app.call_from_thread(
                self._on_search_error,
                str(err) or "Search failed",
            )
            return
        self.app.call_from_thread(self._on_search_success, results)

    @work(thread=True, exclusive=True, group="playback")
    def _play_song(self, song: Song) -> None:
        service = self.playback_service
        if service is None:
            return
        try:
            service.play_song(song)
        except Exception as err:
            self.app.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )

    def _on_search_success(self, results: list[Song]) -> None:
        self._set_loading(False)
        results_list = self.query_one("#results_list", ListView)
        results_list.clear()
        for song in results:
            results_list.append(SongListItem(song))

    def _on_search_error(self, message: str) -> None:
        self._set_loading(False)
        self.notify(message, severity="error")

    def _set_loading(self, is_loading: bool) -> None:
        loading = self.query_one("#search_loading", LoadingIndicator)
        loading.set_class(is_loading, "-visible")
