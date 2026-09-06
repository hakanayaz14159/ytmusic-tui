"""Regressions for player shell failures and background playback ordering."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from textual.widgets import Input
from textual.worker import WorkerCancelled

from tests.conftest import make_test_app
from ytmusic_cli.exceptions import PlaybackError, StreamExtractionError
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import (
    AudioStream,
    PlaybackTick,
    PlaybackTickAction,
    Playlist,
    Song,
    User,
)
from ytmusic_cli.tui.modals.prompt import PromptModal
from ytmusic_cli.tui.shell import AppShell
from ytmusic_cli.tui.widgets.queue_list import QueueList


@pytest.mark.asyncio
async def test_modal_tab_keeps_focus_in_dialog() -> None:
    app = make_test_app()
    async with app.run_test() as pilot:
        shell = app.query_one(AppShell)
        app.push_screen(PromptModal("New playlist"))
        await pilot.pause()
        await pilot.press("tab")
        assert shell.current_mode == "search"
        await pilot.press("shift+tab")
        assert shell.current_mode == "search"
        assert isinstance(app.screen, PromptModal)
        assert app.screen.query_one(Input).has_focus


@pytest.mark.asyncio
async def test_force_quit_works_from_modal() -> None:
    app = make_test_app()
    async with app.run_test() as pilot:
        app.push_screen(PromptModal("New playlist"))
        await pilot.pause()
        await pilot.press("ctrl+q")
        assert not app.is_running


@pytest.mark.parametrize(
    "action", ["action_volume_up", "action_volume_down", "_on_playback_tick"]
)
def test_player_control_errors_are_reported(action: str, mocker: MockerFixture) -> None:
    playback = MagicMock()
    playback.volume_up.side_effect = PlaybackError("Audio device unavailable")
    playback.volume_down.side_effect = PlaybackError("Audio device unavailable")
    playback.sync_playback.side_effect = PlaybackError("Audio device unavailable")
    app = make_test_app(playback_service=playback)
    mocker.patch.object(app, "_insert_if_input", return_value=False)
    notify = mocker.patch.object(app, "notify")

    getattr(app, action)()

    assert "Audio device unavailable" in notify.call_args.args[0]
    assert notify.call_args.kwargs["severity"] == "error"


@pytest.mark.asyncio
async def test_queue_selection_preserves_duplicate_occurrence(
    mock_youtube: MagicMock, mock_player: MagicMock
) -> None:
    song: Song = mock_youtube.search.return_value[0]
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    async with app.run_test() as pilot:
        app.playback_service.set_queue(
            [song, song, mock_youtube.search.return_value[1]]
        )
        app.query_one(AppShell).switch_mode("queue")
        await pilot.pause()
        queue = app.query_one("#queue_table", QueueList)
        queue.set_selected_index(1)
        queue.focus_list()
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        assert AppState().queue_index.get() == 1


@pytest.mark.asyncio
async def test_stream_start_runs_outside_ui_thread(
    mock_youtube: MagicMock, mock_player: MagicMock
) -> None:
    threads: list[int] = []
    mock_player.play.side_effect = lambda _stream: threads.append(threading.get_ident())
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    async with app.run_test():
        app.play_song(mock_youtube.search.return_value[0])
        await app.workers.wait_for_complete()
        assert threads
        assert threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_older_stream_resolution_cannot_replace_newer_song(
    mock_youtube: MagicMock, mock_player: MagicMock
) -> None:
    loop = asyncio.get_running_loop()
    first_started = asyncio.Event()
    first_finished = asyncio.Event()
    release_first = threading.Event()
    songs: list[Song] = mock_youtube.search.return_value

    def resolve(video_id: str) -> AudioStream:
        if video_id == songs[0]["video_id"]:
            loop.call_soon_threadsafe(first_started.set)
            assert release_first.wait(timeout=5)
            loop.call_soon_threadsafe(first_finished.set)
        return {"url": video_id, "http_headers": {}}

    mock_youtube.get_stream.side_effect = resolve
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    async with app.run_test() as pilot:
        try:
            app.play_song(songs[0])
            await asyncio.wait_for(first_started.wait(), timeout=5)
            latest = app.play_song(songs[1])
            await latest.wait()
            release_first.set()
            await asyncio.wait_for(first_finished.wait(), timeout=5)
            await pilot.pause()
            assert AppState().current_song.get() == songs[1]
            assert mock_player.play.call_count == 1
        finally:
            release_first.set()


@pytest.mark.asyncio
async def test_pending_resolution_still_syncs_but_does_not_advance(
    mocker: MockerFixture,
) -> None:
    playback = MagicMock()
    playback.sync_playback.return_value = PlaybackTick(PlaybackTickAction.ENDED)
    app = make_test_app(playback_service=playback)
    async with app.run_test():
        resolver = mocker.patch.object(app, "play_song")
        app._playback_pending = True
        app._on_playback_tick()
        playback.sync_playback.assert_called_once()
        resolver.assert_not_called()


@pytest.mark.asyncio
async def test_app_exit_discards_audio_off_thread_and_commits_on_ui() -> None:
    playback = MagicMock()
    discard_threads: list[int] = []
    commit_threads: list[int] = []
    playback.discard_stream.side_effect = lambda: discard_threads.append(
        threading.get_ident()
    )
    playback.commit_stop.side_effect = lambda: commit_threads.append(
        threading.get_ident()
    )
    app = make_test_app(playback_service=playback)
    ui_thread = threading.get_ident()
    async with app.run_test():
        pass
    assert discard_threads
    assert discard_threads[0] != ui_thread
    assert commit_threads
    assert commit_threads[0] == ui_thread
    playback.stop.assert_not_called()


@pytest.mark.asyncio
async def test_overwrite_confirmation_keeps_original_playlist_and_queue(
    mocker: MockerFixture,
) -> None:
    state = AppState()
    user: User = {
        "id": 1,
        "username": "local",
        "default_volume": 80,
        "search_limit": 10,
    }
    song: Song = {
        "video_id": "one",
        "title": "One",
        "artist": None,
        "album": None,
        "duration": 60,
    }
    working: Playlist = {"id": 1, "name": "Original", "songs": []}
    state.current_user.set(user)
    state.current_playlist.set(working)
    state.queue.set([song])
    app = make_test_app()
    overwrite = mocker.patch.object(app, "_overwrite_worker")
    async with app.run_test() as pilot:
        app.prompt_overwrite_working_playlist()
        await pilot.pause()
        state.current_playlist.set({"id": 2, "name": "Different", "songs": []})
        state.queue.set([])
        await pilot.press("y")
        assert overwrite.call_args.args[0] == 1
        assert overwrite.call_args.args[1] == [song]


@pytest.mark.asyncio
async def test_obsolete_player_start_stops_even_when_new_request_fails(
    mock_youtube: MagicMock, mock_player: MagicMock
) -> None:
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    finished = asyncio.Event()
    release = threading.Event()

    def play(_stream: AudioStream) -> None:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(timeout=5)
        loop.call_soon_threadsafe(finished.set)

    mock_player.play.side_effect = play
    mock_youtube.get_stream.side_effect = [
        {"url": "old", "http_headers": {}},
        StreamExtractionError("Unavailable"),
    ]
    songs: list[Song] = mock_youtube.search.return_value
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    async with app.run_test() as pilot:
        try:
            app.play_song(songs[0])
            await asyncio.wait_for(started.wait(), timeout=5)
            latest = app.play_song(songs[1])
            await latest.wait()
            release.set()
            await asyncio.wait_for(finished.wait(), timeout=5)
            await pilot.pause()
            mock_player.stop.assert_called_once()
            assert AppState().current_song.get() is None
        finally:
            release.set()


@pytest.mark.asyncio
async def test_player_start_failure_clears_previous_playing_state(
    mock_youtube: MagicMock, mock_player: MagicMock
) -> None:
    songs: list[Song] = mock_youtube.search.return_value
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    async with app.run_test():
        await app.play_song(songs[0]).wait()
        mock_player.play.side_effect = PlaybackError("Cannot start stream")
        await app.play_song(songs[1]).wait()
        assert AppState().current_song.get() is None
        assert AppState().playback_state.get()["status"] == "stopped"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["remove", "next", "previous"])
async def test_queue_action_cancels_pending_track(
    action: str, mock_youtube: MagicMock, mock_player: MagicMock
) -> None:
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()
    stream: AudioStream = {"url": "pending", "http_headers": {}}

    def resolve(_video_id: str) -> AudioStream:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(timeout=5)
        return stream

    mock_youtube.get_stream.side_effect = resolve
    songs: list[Song] = mock_youtube.search.return_value
    song = songs[0]
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    async with app.run_test():
        if action == "previous":
            app.playback_service.set_queue(songs, 1)
            pending = app.play_song(songs[1], queue_index=1)
        else:
            app.playback_service.set_queue([song])
            pending = app.play_song(song, queue_index=0)
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            if action == "remove":
                app.remove_from_queue(0)
            elif action == "next":
                app._play_next()
            else:
                app._play_previous()
        finally:
            release.set()
        if action == "previous":
            for worker in list(app.workers):
                try:
                    await worker.wait()
                except WorkerCancelled:
                    continue
            assert AppState().current_song.get() == songs[0]
            mock_player.play.assert_called_once()
            return
        await pending.wait()
        mock_player.play.assert_not_called()
        assert AppState().current_song.get() is None


@pytest.mark.asyncio
async def test_removing_other_duplicate_does_not_cancel_pending_play(
    mock_youtube: MagicMock, mock_player: MagicMock
) -> None:
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()
    stream: AudioStream = {"url": "pending", "http_headers": {}}

    def resolve(_video_id: str) -> AudioStream:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(timeout=5)
        return stream

    mock_youtube.get_stream.side_effect = resolve
    song: Song = mock_youtube.search.return_value[0]
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    async with app.run_test():
        app.playback_service.set_queue([song, song])
        pending = app.play_song(song, queue_index=0)
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            app.remove_from_queue(1)
        finally:
            release.set()
        await pending.wait()
        assert AppState().current_song.get() == song
        mock_player.play.assert_called_once()
        assert AppState().queue.get() == [song]


@pytest.mark.asyncio
async def test_generation_change_before_commit_discards_prepared_audio(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app = make_test_app(mock_youtube=mock_youtube, mock_player=mock_player)
    original_commit = app._begin_playback

    def invalidate_before_commit(song: Song, generation: int) -> object:
        app._cancel_pending_playback()
        return original_commit(song, generation)

    mocker.patch.object(app, "_begin_playback", side_effect=invalidate_before_commit)
    async with app.run_test():
        await app.play_song(mock_youtube.search.return_value[0]).wait()

        mock_player.play.assert_called_once()
        mock_player.stop.assert_called_once()
        assert AppState().current_song.get() is None
