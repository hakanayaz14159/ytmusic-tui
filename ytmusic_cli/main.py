"""Main entry point for YTMusic CLI application."""

import logging
import sys
from typing import ClassVar

import click
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Input

from ytmusic_cli import __version__
from ytmusic_cli.db.bootstrap import bootstrap
from ytmusic_cli.db.repositories import (
    PlaylistRepository,
    SongRepository,
    UserRepository,
)
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
    Playlist,
    Song,
    User,
)
from ytmusic_cli.music.youtube import Youtube
from ytmusic_cli.theme import ytmusic_theme
from ytmusic_cli.tui.modals.add_to_playlist import AddToPlaylistModal
from ytmusic_cli.tui.modals.confirm import ConfirmModal
from ytmusic_cli.tui.modals.help import HelpModal
from ytmusic_cli.tui.modals.prompt import PromptModal
from ytmusic_cli.tui.shell import AppShell
from ytmusic_cli.tui.widgets.song_table import SongTable
from ytmusic_cli.utils.log import configure_logging

logger = logging.getLogger(__name__)


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
        Binding("plus", "volume_up('+')", "Vol +", show=False, priority=True),
        Binding("equals_sign", "volume_up('=')", "Vol +", show=False, priority=True),
        Binding("minus", "volume_down('-')", "Vol -", show=False, priority=True),
        Binding("greater_than", "play_next", "Next", show=False),
        Binding("less_than", "play_previous", "Previous", show=False),
        Binding("1", "mode_search", show=False),
        Binding("2", "mode_queue", show=False),
        Binding("3", "mode_playlists", show=False),
        Binding("4", "mode_profiles", show=False),
        Binding("5", "mode_settings", show=False),
        Binding("tab", "next_mode", show=False, priority=True),
        Binding("shift+tab", "previous_mode", show=False, priority=True),
        Binding("A", "add_to_playlist", show=False),
    ]

    def __init__(
        self,
        search_service: SearchService,
        playback_service: PlaybackService,
        account_service: AccountService,
        playlist_service: PlaylistService,
        settings_service: SettingsService,
    ) -> None:
        super().__init__()
        self.register_theme(ytmusic_theme)
        self.theme = "ytmusic"
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
            logger.exception("toggle failed")
            self.notify(f"Playback failed: {err}", severity="error")

    def action_volume_up(self, char: str = "+") -> None:
        if self._insert_if_input(char):
            return
        self.playback_service.volume_up()

    def action_volume_down(self, char: str = "-") -> None:
        if self._insert_if_input(char):
            return
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

    def action_add_to_playlist(self) -> None:
        if self._insert_if_input("A"):
            return
        song = self._playlist_target_song()
        if song is None:
            self.notify("Nothing to add to a playlist", severity="warning")
            return
        self.add_song_to_playlist(song)

    def on_song_table_append_requested(
        self,
        message: SongTable.AppendRequested,
    ) -> None:
        self.append_song(message.song)

    @work(thread=True, exclusive=True, group="playback")
    def play_song(self, song: Song) -> None:
        logger.info(
            "play requested video_id=%s title=%s",
            song["video_id"],
            song["title"],
        )
        try:
            stream = self.playback_service.resolve_stream(song)
        except YTMusicError as err:
            logger.exception("play resolve failed video_id=%s", song["video_id"])
            self.call_from_thread(
                self.notify,
                f"Playback failed: {err}",
                severity="error",
            )
            return
        self.call_from_thread(self._begin_playback, song, stream)

    def append_song(self, song: Song) -> None:
        logger.info(
            "append requested video_id=%s title=%s",
            song["video_id"],
            song["title"],
        )
        status = AppState().playback_state.get()["status"]
        self.playback_service.enqueue(song)
        if status != PlaybackStatus.STOPPED:
            self.notify(f"Queued: {song['title']}", severity="information")
            return
        self.play_song(song)

    def load_playlist_into_queue(
        self,
        playlist_id: int,
        *,
        play: bool,
        start_index: int = 0,
    ) -> None:
        if self._require_playlist_user() is None:
            return
        self._load_playlist_worker(playlist_id, play, start_index)

    @work(thread=True, exclusive=True, group="playlist-io")
    def _load_playlist_worker(
        self,
        playlist_id: int,
        play: bool,
        start_index: int,
    ) -> None:
        try:
            playlist = self.playlist_service.get_playlist(playlist_id)
        except YTMusicError as err:
            logger.exception("playlist load failed id=%s", playlist_id)
            self.call_from_thread(self.notify, str(err), severity="error")
            return
        self.call_from_thread(
            self._on_playlist_loaded,
            playlist,
            play,
            start_index,
        )

    def _on_playlist_loaded(
        self,
        playlist: Playlist,
        play: bool,
        start_index: int,
    ) -> None:
        self.playlist_service.adopt_working_playlist(playlist)
        if play:
            self.play_playlist(playlist["songs"], start_index)
            return
        self.playback_service.load_queue(playlist["songs"])
        self.notify(f"Working: {playlist['name']}", severity="information")

    def prompt_open_working_playlist(self) -> None:
        user = self._require_playlist_user()
        if user is None:
            return
        self._prompt_open_worker(user["id"])

    @work(thread=True, exclusive=True, group="playlist-io")
    def _prompt_open_worker(self, user_id: int) -> None:
        try:
            playlists = self.playlist_service.list_playlists(user_id)
        except YTMusicError as err:
            logger.exception("playlist list for open failed")
            self.call_from_thread(self.notify, str(err), severity="error")
            return
        self.call_from_thread(self._show_open_playlist_modal, playlists)

    def _show_open_playlist_modal(self, playlists: list[Playlist]) -> None:
        self.push_screen(
            AddToPlaylistModal(playlists, title="Open playlist"),
            self._on_open_working_playlist,
        )

    def prompt_save_queue_as_playlist(self) -> None:
        if not AppState().queue.get():
            self.notify("Queue is empty", severity="warning")
            return
        if self._require_playlist_user() is None:
            return
        self.push_screen(
            PromptModal("Save queue as playlist", "Name"),
            self._on_save_queue_name,
        )

    def prompt_overwrite_working_playlist(self) -> None:
        working = AppState().current_playlist.get()
        if working is None:
            self.notify(
                "No working playlist. Press o to open one or n to save as new.",
                severity="warning",
            )
            return
        self.push_screen(
            ConfirmModal(f"Overwrite “{working['name']}” with the current queue?"),
            self._on_confirm_overwrite_working,
        )

    def save_queue_as_playlist(self, name: str) -> None:
        user = self._require_playlist_user()
        if user is None:
            return
        self._save_queue_worker(name, user["id"], list(AppState().queue.get()))

    @work(thread=True, exclusive=True, group="playlist-io")
    def _save_queue_worker(
        self,
        name: str,
        user_id: int,
        songs: list[Song],
    ) -> None:
        try:
            playlist = self.playlist_service.create_playlist_from_songs(
                user_id,
                name,
                songs,
            )
        except YTMusicError as err:
            logger.exception("queue save as playlist failed")
            self.call_from_thread(self.notify, str(err), severity="error")
            return
        self.call_from_thread(self._on_playlist_saved, playlist)

    def _on_playlist_saved(self, playlist: Playlist) -> None:
        self.playlist_service.adopt_working_playlist(playlist)
        self.notify(f"Saved playlist {playlist['name']}", severity="information")

    def overwrite_working_playlist(self) -> None:
        user = self._require_playlist_user()
        working = AppState().current_playlist.get()
        if user is None or working is None:
            return
        self._overwrite_worker(working["id"], list(AppState().queue.get()))

    @work(thread=True, exclusive=True, group="playlist-io")
    def _overwrite_worker(self, playlist_id: int, songs: list[Song]) -> None:
        try:
            playlist = self.playlist_service.replace_songs(playlist_id, songs)
        except YTMusicError as err:
            logger.exception("working playlist overwrite failed")
            self.call_from_thread(self.notify, str(err), severity="error")
            return
        self.call_from_thread(self._on_playlist_overwritten, playlist)

    def _on_playlist_overwritten(self, playlist: Playlist) -> None:
        self.playlist_service.adopt_working_playlist(playlist)
        self.notify(f"Updated {playlist['name']}", severity="information")

    def play_playlist(self, songs: list[Song], start_index: int) -> None:
        logger.info("playlist play count=%s start_index=%s", len(songs), start_index)
        try:
            song = self.playback_service.set_queue(songs, start_index)
        except YTMusicError as err:
            logger.exception("playlist play failed")
            self.notify(f"Playback failed: {err}", severity="error")
            return
        self.play_song(song)

    def remove_from_queue(self, index: int) -> None:
        try:
            song = self.playback_service.remove_from_queue(index)
        except YTMusicError as err:
            logger.exception("queue remove failed index=%s", index)
            self.notify(str(err), severity="error")
            return
        if song is not None:
            self.play_song(song)

    def add_song_to_playlist(self, song: Song) -> None:
        user = self._require_playlist_user()
        if user is None:
            return
        self._list_playlists_for_add(song, user["id"])

    @work(thread=True, exclusive=True, group="playlist-io")
    def _list_playlists_for_add(self, song: Song, user_id: int) -> None:
        try:
            playlists = self.playlist_service.list_playlists(user_id)
        except YTMusicError as err:
            logger.exception("playlist list for add failed")
            self.call_from_thread(self.notify, str(err), severity="error")
            return
        self.call_from_thread(self._show_add_to_playlist_modal, song, playlists)

    def _show_add_to_playlist_modal(
        self,
        song: Song,
        playlists: list[Playlist],
    ) -> None:
        def _on_pick(playlist_id: int | None) -> None:
            if playlist_id is None:
                return
            self._add_song_worker(playlist_id, song)

        self.push_screen(AddToPlaylistModal(playlists), _on_pick)

    @work(thread=True, exclusive=True, group="playlist-io")
    def _add_song_worker(self, playlist_id: int, song: Song) -> None:
        try:
            self.playlist_service.add_song(playlist_id, song)
        except YTMusicError as err:
            logger.exception("playlist add failed id=%s", playlist_id)
            self.call_from_thread(self.notify, str(err), severity="error")
            return
        self.call_from_thread(
            self.notify,
            "Added to playlist",
            severity="information",
        )

    def _begin_playback(self, song: Song, stream: AudioStream) -> None:
        try:
            self.playback_service.start_stream(song, stream)
        except YTMusicError as err:
            logger.exception("start_stream failed video_id=%s", song["video_id"])
            self.notify(f"Playback failed: {err}", severity="error")
            return
        logger.info(
            "playback started video_id=%s title=%s",
            song["video_id"],
            song["title"],
        )
        self.notify(f"Playing: {song['title']}", severity="information")

    def _on_playback_tick(self) -> None:
        tick = self.playback_service.sync_playback()
        if tick.action == PlaybackTickAction.FAILED:
            logger.error("playback tick failed message=%s", tick.message)
            self.notify(tick.message or "Playback failed", severity="error")
        elif tick.action == PlaybackTickAction.ENDED:
            logger.info("playback tick ended")
            self._play_next()

    def _replay_current(self) -> None:
        song = AppState().current_song.get()
        if song is None:
            return
        logger.info("replay requested video_id=%s", song["video_id"])
        self.play_song(song)

    def _play_next(self) -> None:
        logger.info("play next requested")
        try:
            song = self.playback_service.advance_to_next()
        except YTMusicError as err:
            logger.exception("play next failed")
            self.notify(f"Playback failed: {err}", severity="error")
            return
        if song is None:
            return
        self.play_song(song)

    def _play_previous(self) -> None:
        logger.info("play previous requested")
        try:
            song = self.playback_service.advance_to_previous()
        except YTMusicError as err:
            logger.exception("play previous failed")
            self.notify(f"Playback failed: {err}", severity="error")
            return
        if song is None:
            return
        self.play_song(song)

    def _require_playlist_user(self) -> User | None:
        user = AppState().current_user.get()
        if user is None:
            self.notify("Create a profile to use playlists", severity="warning")
            self._shell().switch_mode("profiles")
            return None
        return user

    def _playlist_target_song(self) -> Song | None:
        focused = self.focused
        if focused is not None:
            for node in focused.ancestors_with_self:
                if isinstance(node, SongTable):
                    selected = node.get_selected_song()
                    if selected is not None:
                        return selected
                    break
        return AppState().current_song.get()

    def _on_open_working_playlist(self, playlist_id: int | None) -> None:
        if playlist_id is None:
            return
        self.load_playlist_into_queue(playlist_id, play=False)

    def _on_save_queue_name(self, name: str | None) -> None:
        if name is None:
            return
        self.save_queue_as_playlist(name)

    def _on_confirm_overwrite_working(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.overwrite_working_playlist()

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
        playlist_service=PlaylistService(PlaylistRepository(SongRepository()), state),
        settings_service=SettingsService(users, state),
    )


@click.command()
@click.version_option(version=__version__)
def main() -> None:
    """YTMusic CLI — a terminal music player for YouTube audio."""

    try:
        log_path = configure_logging()
        if log_path is not None:
            logger.info("logging to %s", log_path)
        logger.info("starting ytmusic-cli")
        bootstrap()
        app = build_production_app()
        app.run()
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        logger.exception("fatal error")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
