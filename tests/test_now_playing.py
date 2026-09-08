"""Textual pilot tests for the NowPlaying widget."""

import threading

import pytest
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import PlaybackStatus, Song
from ytmusic_tui.tui.modes.queue import QueueMode
from ytmusic_tui.tui.widgets.mode_bar import ModeBar
from ytmusic_tui.tui.widgets.now_playing import NowPlaying
from ytmusic_tui.tui.widgets.select_list import SelectList


class NowPlayingApp(App[None]):
    def compose(self) -> ComposeResult:
        yield NowPlaying(id="now_playing")


class MetadataWidgetsApp(App[None]):
    CSS = """
    NowPlaying { height: 3; }
    ModeBar { height: 1; }
    QueueMode { height: 4; }
    SelectList { height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield NowPlaying()
        yield ModeBar()
        yield QueueMode()
        yield SelectList("[b]Mix[/b]", id="metadata_options", markup=False)


def _bar_text(app: App[None]) -> str:
    bar = app.query_one(NowPlaying)
    parts = [
        str(bar.query_one("#np_title", Static).content),
        str(bar.query_one("#np_detail", Static).content),
    ]
    return " ".join(parts)


@pytest.mark.asyncio
async def test_now_playing_initial_display_shows_stopped_empty_state() -> None:
    app = NowPlayingApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        text = _bar_text(app)
        assert "■" in text
        assert "[No track playing]" in text
        assert "80%" in text


@pytest.mark.asyncio
async def test_now_playing_updates_when_app_state_changes() -> None:
    app = NowPlayingApp()
    song: Song = {
        "video_id": "synth42",
        "title": "Ambient Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 210,
    }

    async with app.run_test() as pilot:
        await pilot.pause()
        state = AppState()
        state.current_song.set(song)
        state.playback_state.set(
            {
                "status": PlaybackStatus.PLAYING,
                "volume": 65,
                "position": 45.0,
                "duration": 210,
            }
        )
        await pilot.pause()

        text = _bar_text(app)
        assert "▶" in text
        assert "Ambient Flow" in text
        assert "SynthArtist" in text
        assert "65%" in text
        assert "00:45 / 03:30" in text

        state.playback_state.set(
            {
                "status": PlaybackStatus.PAUSED,
                "volume": 65,
                "position": 45.0,
                "duration": 210,
            }
        )
        await pilot.pause()
        text = _bar_text(app)
        assert "⏸" in text


@pytest.mark.asyncio
async def test_now_playing_unmount_unsubscribes_without_errors() -> None:
    app = NowPlayingApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        state = AppState()
        assert len(state.current_song._subscribers) == 1
        assert len(state.playback_state._subscribers) == 1

        bar = app.query_one(NowPlaying)
        await bar.remove()
        await pilot.pause()

        assert len(state.current_song._subscribers) == 0
        assert len(state.playback_state._subscribers) == 0

        state.current_song.set(None)
        state.playback_state.set(
            {
                "status": PlaybackStatus.STOPPED,
                "volume": 80,
                "position": 0.0,
                "duration": 0,
            }
        )
        await pilot.pause()


@pytest.mark.asyncio
async def test_now_playing_updates_when_state_changed_from_worker_thread() -> None:
    app = NowPlayingApp()
    song: Song = {
        "video_id": "thread99",
        "title": "Thread Song",
        "artist": "Thread Artist",
        "album": "Thread Album",
        "duration": 150,
    }
    async with app.run_test() as pilot:
        await pilot.pause()
        state = AppState()

        def _update() -> None:
            state.current_song.set(song)
            state.playback_state.set(
                {
                    "status": PlaybackStatus.PLAYING,
                    "volume": 75,
                    "position": 10.0,
                    "duration": 150,
                }
            )

        worker = threading.Thread(target=_update)
        worker.start()
        worker.join()

        await pilot.pause()
        await pilot.pause()

        text = _bar_text(app)
        assert "▶" in text
        assert "Thread Song" in text
        assert "75%" in text


@pytest.mark.asyncio
async def test_now_playing_uses_unknown_uploader_when_artist_missing() -> None:
    app = NowPlayingApp()
    song: Song = {
        "video_id": "none01",
        "title": "No Credit",
        "artist": None,
        "album": None,
        "duration": 90,
    }

    async with app.run_test() as pilot:
        await pilot.pause()
        state = AppState()
        state.current_song.set(song)
        state.playback_state.set(
            {
                "status": PlaybackStatus.PLAYING,
                "volume": 50,
                "position": 0.0,
                "duration": 90,
            }
        )
        await pilot.pause()

        text = _bar_text(app)
        assert "Unknown Uploader" in text
        assert "Unknown Artist" not in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("#np_title", "[b]Track[/b]"),
        ("#np_title", "[b]Uploader[/b]"),
        ("#mode_user", "[b]User[/b]"),
        ("#queue_working", "[b]Mix[/b]"),
        ("#metadata_options", "[b]Mix[/b]"),
    ],
)
async def test_metadata_widgets_render_names_as_literal_text(
    selector: str, expected: str
) -> None:
    state = AppState()
    state.current_song.set(
        Song(
            video_id="track",
            title="[b]Track[/b]",
            artist="[b]Uploader[/b]",
            album=None,
            duration=120,
        )
    )
    state.current_user.set(
        {"id": 1, "username": "[b]User[/b]", "default_volume": 80, "search_limit": 10}
    )
    state.current_playlist.set({"id": 1, "name": "[b]Mix[/b]", "songs": []})
    app = MetadataWidgetsApp()
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        widget = app.query_one(selector, Widget)
        rendered = "".join(
            widget.render_line(y).text for y in range(widget.size.height)
        )

        assert expected in rendered
