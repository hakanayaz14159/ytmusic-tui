"""Textual pilot tests for the PlayerBar mini-player widget."""

import threading

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackStatus, Song
from ytmusic_cli.tui.player_bar import PlayerBar


class PlayerBarApp(App[None]):
    """Minimal app that mounts only PlayerBar for isolated pilot tests."""

    def compose(self) -> ComposeResult:
        yield PlayerBar()


def _bar_text(app: App[None]) -> str:
    """Concatenate PlayerBar child Static contents for assertions."""
    bar = app.query_one(PlayerBar)
    parts = [
        str(bar.query_one("#player_status", Static).content),
        str(bar.query_one("#player_track", Static).content),
        str(bar.query_one("#player_progress", Static).content),
        str(bar.query_one("#player_volume", Static).content),
    ]
    return " ".join(parts)


@pytest.mark.asyncio
async def test_player_bar_initial_display_shows_stopped_empty_state() -> None:
    app = PlayerBarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        text = _bar_text(app)
        assert "■" in text
        assert "[No track playing]" in text
        assert "[Vol: 80%]" in text


@pytest.mark.asyncio
async def test_player_bar_updates_when_app_state_changes() -> None:
    app = PlayerBarApp()
    song: Song = {
        "id": 42,
        "title": "Ambient Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 210,
        "url": "https://www.youtube.com/watch?v=synth42",
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
        assert "Ambient Flow - SynthArtist" in text
        assert "[Vol: 65%]" in text
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
async def test_player_bar_unmount_unsubscribes_without_errors() -> None:
    app = PlayerBarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        state = AppState()
        assert len(state.current_song._subscribers) == 1
        assert len(state.playback_state._subscribers) == 1

        bar = app.query_one(PlayerBar)
        await bar.remove()
        await pilot.pause()

        assert len(state.current_song._subscribers) == 0
        assert len(state.playback_state._subscribers) == 0

        # Setting state after unmount must not raise
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
async def test_player_bar_updates_when_state_changed_from_worker_thread() -> None:
    app = PlayerBarApp()
    song: Song = {
        "id": 99,
        "title": "Thread Song",
        "artist": "Thread Artist",
        "album": "Thread Album",
        "duration": 150,
        "url": "https://www.youtube.com/watch?v=thread99",
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
        assert "Thread Song - Thread Artist" in text
        assert "[Vol: 75%]" in text
