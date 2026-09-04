"""Tests for PlaybackState domain types and AppState extension."""

from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackState, PlaybackStatus


def test_playback_status_enum_values() -> None:
    assert PlaybackStatus.STOPPED.value == "stopped"
    assert PlaybackStatus.PLAYING.value == "playing"
    assert PlaybackStatus.PAUSED.value == "paused"


def test_app_state_default_playback_state() -> None:
    state = AppState()
    state.reset()
    playback = state.playback_state.get()
    assert playback["status"] == PlaybackStatus.STOPPED
    assert playback["volume"] == 80
    assert playback["position"] == 0.0
    assert playback["duration"] == 0


def test_app_state_playback_state_set_notifies_subscribers() -> None:
    state = AppState()
    state.reset()
    received: list[PlaybackState] = []

    def on_change(value: PlaybackState) -> None:
        received.append(value)

    state.playback_state.subscribe(on_change)
    updated: PlaybackState = {
        "status": PlaybackStatus.PLAYING,
        "volume": 60,
        "position": 12.5,
        "duration": 200,
    }
    state.playback_state.set(updated)

    assert len(received) == 1
    assert received[0] == updated
    assert state.playback_state.get() == updated


def test_app_state_playback_unsubscribe_stops_notifications() -> None:
    state = AppState()
    state.reset()
    received: list[PlaybackState] = []

    def on_change(value: PlaybackState) -> None:
        received.append(value)

    unsubscribe = state.playback_state.subscribe(on_change)
    unsubscribe()
    state.playback_state.set(
        {
            "status": PlaybackStatus.PAUSED,
            "volume": 50,
            "position": 1.0,
            "duration": 100,
        }
    )
    assert received == []


def test_app_state_reset_restores_playback_defaults() -> None:
    state = AppState()
    state.playback_state.set(
        {
            "status": PlaybackStatus.PLAYING,
            "volume": 10,
            "position": 99.0,
            "duration": 300,
        }
    )
    state.current_song.set(
        {
            "video_id": "abc",
            "title": "Test",
            "artist": "Artist",
            "album": None,
            "duration": 300,
        }
    )
    state.reset()
    playback = state.playback_state.get()
    assert playback["status"] == PlaybackStatus.STOPPED
    assert playback["volume"] == 80
    assert playback["position"] == 0.0
    assert playback["duration"] == 0
    assert state.current_song.get() is None
