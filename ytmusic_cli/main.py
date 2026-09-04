"""Main entry point for YTMusic CLI application."""

import sys
from typing import Any, ClassVar

import click
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Input

from ytmusic_cli import __version__
from ytmusic_cli.db.bootstrap import bootstrap
from ytmusic_cli.db.repositories import PlaylistRepository, UserRepository
from ytmusic_cli.exceptions import YTMusicError
from ytmusic_cli.music.player import VLCPlayer
from ytmusic_cli.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
    SettingsService,
)
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import (
    AudioStream,
    PlaybackStatus,
    PlaybackTickAction,
    Song,
)
from ytmusic_cli.music.youtube import Youtube
from ytmusic_cli.theme import ytmusic_theme
from ytmusic_cli.tui.modals.add_to_playlist import AddToPlaylistModal
from ytmusic_cli.tui.modals.help import HelpModal
from ytmusic_cli.tui.shell import AppShell
from ytmusic_cli.tui.widgets.song_table import SongTable


class YTMusicApp(App[None]):
    """Search-first terminal music player."""

    TITLE = "YTMusic"
    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit_player", "Quit", show=False),
        Binding("ctrl+q", "force_quit", "Quit", show=False),
        Binding("slash", "focus_search", "Search", show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("space", "toggle_playback", "Play/Pause", show=False),
        Binding("plus", "volume_up", "Vol +", show=False, priority=True),
        Binding("equals_sign", "volume_up", "Vol +", show=False, priority=True),
        Binding("minus", "volume_down", "Vol -", show=False, priority=True),
        Binding("greater_than", "play_next", "Next", show=False),
        Binding("less_than", "play_previous", "Previous", show=False),
        Binding("1", "mode_search", show=False),
        Binding("2", "mode_queue", show=False),
        Binding("3", "mode_playlists", show=False),
        Binding("4", "mode_profiles", show=False),
        Binding("5", "mode_settings", show=False),
        Binding("tab", "next_mode", show=False, priority=True),
        Binding("shift+tab", "previous_mode", show=False, priority=True),
    ]

    def __init__(
        self,
        *args: Any,
        search_service: SearchService | None = None,
        playback_service: PlaybackService | None = None,
        account_service: AccountService | None = None,
        playlist_service: PlaylistService | None = None,
        settings_service: SettingsService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.register_theme(ytmusic_theme)
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
        self.account_service = account_service
        self.playlist_service = playlist_service
        self.settings_service = settings_service

    def on_mount(self) -> None:
        self.set_interval(1.0, self._on_playback_tick)

    def compose(self) -> ComposeResult:
        yield AppShell(id="app_shell")

    def action_focus_search(self) -> None:
        if self._insert_if_input("/"):
            return
        self._shell().switch_mode("search")
        self.query_one("#search_input", Input).focus()

    def action_quit_player(self) -> None:
        if self._focused_is_input():
            return
        self.exit()

    def action_force_quit(self) -> None:
        self.exit()

    def action_help(self) -> None:
        if self._insert_if_input("?"):
            return
        self.push_screen(HelpModal())

    def action_toggle_playback(self) -> None:
        if self._insert_if_input(" "):
            return
        status = AppState().playback_state.get()["status"]
        if (
            status == PlaybackStatus.STOPPED
            and AppState().current_song.get() is not None
        ):
            self._replay_current()
            return
        try:
            self.playback_service.toggle()
        except YTMusicError as err:
            self.notify(f"Playback failed: {err}", severity="error")

    def action_volume_up(self) -> None:
        self.playback_service.volume_up()

    def action_volume_down(self) -> None:
        self.playback_service.volume_down()

    def action_play_next(self) -> None:
        if self._insert_if_input(">"):
            return
        self._play_next()

    def action_play_previous(self) -> None:
        if self._insert_if_input("<"):
            return
        self._play_previous()

    def action_mode_search(self) -> None:
        if self._insert_if_input("1"):
            return
        self._shell().switch_mode("search")

    def action_mode_queue(self) -> None:
        if self._insert_if_input("2"):
            return
        self._shell().switch_mode("queue")

    def action_mode_playlists(self) -> None:
        if self._insert_if_input("3"):
            return
        self._shell().switch_mode("playlists")

    def action_mode_profiles(self) -> None:
        if self._insert_if_input("4"):
            return
        self._shell().switch_mode("profiles")

    def action_mode_settings(self) -> None:
        if self._insert_if_input("5"):
            return
        self._shell().switch_mode("settings")

    def action_next_mode(self) -> None:
        self._shell().next_mode()

    def action_previous_mode(self) -> None:
        self._shell().previous_mode()

    def on_song_table_append_requested(
        self,
        message: SongTable.AppendRequested,
    ) -> None:
        self.append_song(message.song)

    def on_song_table_playlist_requested(
        self,
        message: SongTable.PlaylistRequested,
    ) -> None:
        self.add_song_to_playlist(message.song)

    @work(thread=True, exclusive=True, group="playback")
    def play_song(self, song: Song) -> None:
        try:
            stream = self.playback_service.resolve_stream(song)
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(self._begin_playback, song, stream)

    @work(thread=True, exclusive=True, group="playback")
    def append_song(self, song: Song) -> None:
        status = AppState().playback_state.get()["status"]
        self.playback_service.enqueue(song)
        if status != PlaybackStatus.STOPPED:
            self.call_from_thread(
                self.notify,
                f"Queued: {song['title']}",
                severity="information",
            )
            return
        try:
            stream = self.playback_service.resolve_stream(song)
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Queue failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(self._begin_playback, song, stream)

    @work(thread=True, exclusive=True, group="playback")
    def play_playlist(self, songs: list[Song], start_index: int) -> None:
        try:
            song = self.playback_service.set_queue(songs, start_index)
            stream = self.playback_service.resolve_stream(song)
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(self._begin_playback, song, stream)

    def remove_from_queue(self, index: int) -> None:
        try:
            song = self.playback_service.remove_from_queue(index)
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        if song is not None:
            self.play_song(song)

    def add_song_to_playlist(self, song: Song) -> None:
        if self.playlist_service is None:
            self.notify("Playlists are unavailable", severity="warning")
            return
        user = AppState().current_user.get()
        if user is None:
            self.notify("Create a profile to use playlists", severity="warning")
            self._shell().switch_mode("profiles")
            return
        playlists = self.playlist_service.list_playlists(user["id"])

        def _on_pick(playlist_id: int | None) -> None:
            if playlist_id is None or self.playlist_service is None:
                return
            try:
                self.playlist_service.add_song(playlist_id, song)
            except YTMusicError as err:
                self.notify(str(err), severity="error")
                return
            self.notify("Added to playlist", severity="information")

        self.push_screen(AddToPlaylistModal(playlists), _on_pick)

    def _begin_playback(self, song: Song, stream: AudioStream) -> None:
        try:
            self.playback_service.start_stream(song, stream)
        except YTMusicError as err:
            self.notify(f"Playback failed: {err}", severity="error")
            return
        self.notify(f"Playing: {song['title']}", severity="information")

    def _on_playback_tick(self) -> None:
        tick = self.playback_service.sync_playback()
        if tick.action == PlaybackTickAction.FAILED:
            self.notify(tick.message or "Playback failed", severity="error")
        elif tick.action == PlaybackTickAction.ENDED:
            self._play_next()

    @work(thread=True, exclusive=True, group="playback")
    def _replay_current(self) -> None:
        song = AppState().current_song.get()
        if song is None:
            return
        try:
            stream = self.playback_service.resolve_stream(song)
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(self._begin_playback, song, stream)

    @work(thread=True, exclusive=True, group="playback")
    def _play_next(self) -> None:
        try:
            song = self.playback_service.advance_to_next()
            if song is None:
                return
            stream = self.playback_service.resolve_stream(song)
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(self._begin_playback, song, stream)

    @work(thread=True, exclusive=True, group="playback")
    def _play_previous(self) -> None:
        try:
            song = self.playback_service.advance_to_previous()
            if song is None:
                return
            stream = self.playback_service.resolve_stream(song)
        except YTMusicError as err:
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(self._begin_playback, song, stream)

    def _shell(self) -> AppShell:
        return self.query_one(AppShell)

    def _focused_is_input(self) -> bool:
        return isinstance(self.focused, Input)

    def _insert_if_input(self, text: str) -> bool:
        focused = self.focused
        if not isinstance(focused, Input):
            return False
        focused.insert_text_at_cursor(text)
        return True


def build_production_app() -> YTMusicApp:
    state = AppState()
    source = Youtube()
    player = VLCPlayer()
    users = UserRepository()
    return YTMusicApp(
        search_service=SearchService(source),
        playback_service=PlaybackService(player, source, state),
        account_service=AccountService(users, state),
        playlist_service=PlaylistService(PlaylistRepository()),
        settings_service=SettingsService(users, state),
    )


@click.command()
@click.version_option(version=__version__)
def main() -> None:
    """YTMusic CLI — a terminal music player for YouTube audio."""

    try:
        bootstrap()
        app = build_production_app()
        app.run()
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
