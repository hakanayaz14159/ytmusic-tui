"""Main entry point for YTMusic CLI application."""

import sys
from typing import Any, ClassVar

import click
from textual import work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Center
from textual.widgets import Footer

from ytmusic_cli.db.bootstrap import bootstrap
from ytmusic_cli.exceptions import YTMusicError
from ytmusic_cli.music.player import VLCPlayer
from ytmusic_cli.music.services import PlaybackService, SearchService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Song
from ytmusic_cli.music.youtube import Youtube
from ytmusic_cli.theme import ytmusic_theme
from ytmusic_cli.tui.ascii_title import AsciiTitle
from ytmusic_cli.tui.header import Header
from ytmusic_cli.tui.main_menu import MainMenu
from ytmusic_cli.tui.player_bar import PlayerBar
from ytmusic_cli.tui.search_screen import SearchScreen

from . import __version__


class YTMusicApp(App[None]):
    """Main Textual application for YTMusic CLI."""

    TITLE = "YTMusic CLI"
    SUB_TITLE = "YouTube Music Terminal Interface"
    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        ("q", "quit", "Quit"),
        ("a", "accounts", "Accounts"),
        ("p", "playlists", "Playlists"),
        ("s", "search", "Search"),
        ("/", "search", "Search"),
        ("space", "toggle_playback", "Play/Pause"),
        ("+", "volume_up", "Vol +"),
        ("=", "volume_up", "Vol +"),
        ("-", "volume_down", "Vol -"),
        ("h", "help", "Help"),
    ]

    def __init__(
        self,
        *args: Any,
        search_service: SearchService | None = None,
        playback_service: PlaybackService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        # Register our custom theme
        self.register_theme(ytmusic_theme)
        # Set it as the default theme
        self.theme = "ytmusic"

        if search_service is None or playback_service is None:
            source = Youtube()
            player = VLCPlayer()
            search_service = search_service or SearchService(source=source)
            playback_service = playback_service or PlaybackService(
                player=player,
                source=source,
                state=AppState(),
            )

        self.search_service = search_service
        self.playback_service = playback_service

    def on_mount(self) -> None:
        self.set_interval(1.0, self.playback_service.sync_playback)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Center(AsciiTitle(), id="ascii_title")
        yield MainMenu(id="main_menu")
        yield PlayerBar(id="player_bar")
        yield Footer()

    def action_search(self) -> None:
        """Open search interface."""
        self.push_screen(SearchScreen(search_service=self.search_service))

    @work(thread=True, exclusive=True, group="playback")
    def play_song(self, song: Song) -> None:
        try:
            self.playback_service.play_song(song)
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(
            self.notify,
            f"Playing: {song['title']}",
            severity="information",
        )

    @work(thread=True, exclusive=True, group="playback")
    def action_toggle_playback(self) -> None:
        """Toggle play/pause on the current track."""
        try:
            self.playback_service.toggle()
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )

    def action_volume_up(self) -> None:
        """Increase playback volume."""
        self.playback_service.volume_up()

    def action_volume_down(self) -> None:
        """Decrease playback volume."""
        self.playback_service.volume_down()

    def action_playlists(self) -> None:
        """Show playlists."""
        self.bell()
        # TODO: Implement playlist functionality

    def action_accounts(self) -> None:
        """Show accounts."""
        self.bell()
        # TODO: Implement accounts functionality

    def action_help(self) -> None:
        """Show help."""
        self.bell()
        # TODO: Implement help screen


@click.command()
@click.version_option(version=__version__)
def main() -> None:
    """YTMusic CLI - A modern terminal interface for YouTube Music.

    Use arrow keys to navigate, Enter to select, and 'q' to quit.
    """

    try:
        bootstrap()
        app = YTMusicApp()
        app.run()
    except KeyboardInterrupt:
        click.echo("\nGoodbye! 🎵")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
