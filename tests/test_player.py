"""Tests for VLCPlayer audio adapter (mocked VLC, no hardware)."""

from unittest.mock import MagicMock

import pytest
import vlc
from pytest_mock import MockerFixture

from ytmusic_cli.exceptions import PlaybackError
from ytmusic_cli.music.player import VLCPlayer
from ytmusic_cli.music.ports import AudioPlayerProtocol
from ytmusic_cli.music.types import AudioStream


@pytest.fixture
def mock_vlc(mocker: MockerFixture) -> MagicMock:
    """Patch vlc.Instance and return the mock media player."""
    mock_instance = mocker.MagicMock()
    mock_media_player = mocker.MagicMock()
    mock_media = mocker.MagicMock()
    mock_media_player.play.return_value = 0
    mock_instance.media_player_new.return_value = mock_media_player
    mock_instance.media_new.return_value = mock_media
    mocker.patch("ytmusic_cli.music.player.vlc.Instance", return_value=mock_instance)
    return mock_media_player


def test_vlc_player_implements_audio_player_protocol(mock_vlc: MagicMock) -> None:
    player = VLCPlayer()
    assert isinstance(player, AudioPlayerProtocol)
    assert mock_vlc is player._player


def test_init_passes_no_video_option(mocker: MockerFixture) -> None:
    mock_instance_cls = mocker.patch("ytmusic_cli.music.player.vlc.Instance")
    VLCPlayer()
    mock_instance_cls.assert_called_once()
    args = mock_instance_cls.call_args[0]
    assert "--no-video" in args


def test_play_sets_media_configures_headers_and_plays(mock_vlc: MagicMock) -> None:
    player = VLCPlayer()
    stream: AudioStream = {
        "url": "https://stream.example.com/audio.m4a",
        "http_headers": {
            "User-Agent": "test-agent",
            "Referer": "https://www.youtube.com/",
        },
    }
    player.play(stream)
    player._instance.media_new.assert_called_once_with(
        "https://stream.example.com/audio.m4a"
    )
    mock_media = player._instance.media_new.return_value
    mock_media.add_option.assert_any_call(":http-user-agent=test-agent")
    mock_media.add_option.assert_any_call(":http-referrer=https://www.youtube.com/")
    mock_vlc.set_media.assert_called_once_with(mock_media)
    mock_vlc.play.assert_called_once()


def test_play_raises_playback_error_when_vlc_returns_failure_code(
    mock_vlc: MagicMock,
) -> None:
    mock_vlc.play.return_value = -1
    player = VLCPlayer()
    stream: AudioStream = {
        "url": "https://stream.example.com/audio.m4a",
        "http_headers": {},
    }
    with pytest.raises(PlaybackError, match="Failed to play"):
        player.play(stream)


def test_pause_delegates_to_vlc(mock_vlc: MagicMock) -> None:
    player = VLCPlayer()
    player.pause()
    mock_vlc.pause.assert_called_once()


def test_stop_delegates_to_vlc(mock_vlc: MagicMock) -> None:
    player = VLCPlayer()
    player.stop()
    mock_vlc.stop.assert_called_once()


def test_is_playing_delegates_to_vlc(mock_vlc: MagicMock) -> None:
    mock_vlc.is_playing.return_value = 1
    player = VLCPlayer()
    assert player.is_playing() is True
    mock_vlc.is_playing.return_value = 0
    assert player.is_playing() is False


def test_set_volume_clamps_to_0_100(mock_vlc: MagicMock) -> None:
    player = VLCPlayer()
    player.set_volume(150)
    mock_vlc.audio_set_volume.assert_called_with(100)
    player.set_volume(-10)
    mock_vlc.audio_set_volume.assert_called_with(0)
    player.set_volume(55)
    mock_vlc.audio_set_volume.assert_called_with(55)


def test_get_volume_delegates_to_vlc(mock_vlc: MagicMock) -> None:
    mock_vlc.audio_get_volume.return_value = 72
    player = VLCPlayer()
    assert player.get_volume() == 72


def test_play_wraps_vlc_errors_as_playback_error(mock_vlc: MagicMock) -> None:
    mock_vlc.play.side_effect = RuntimeError("libvlc boom")
    player = VLCPlayer()
    stream: AudioStream = {
        "url": "https://stream.example.com/audio.m4a",
        "http_headers": {},
    }
    with pytest.raises(PlaybackError, match="Failed to play") as exc_info:
        player.play(stream)
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_get_position_converts_milliseconds_to_seconds(mock_vlc: MagicMock) -> None:
    mock_vlc.get_time.return_value = 4500
    player = VLCPlayer()
    assert player.get_position() == 4.5


def test_get_position_clamps_negative_time_to_zero(mock_vlc: MagicMock) -> None:
    mock_vlc.get_time.return_value = -1
    player = VLCPlayer()
    assert player.get_position() == 0.0


def test_get_position_wraps_vlc_errors_as_playback_error(mock_vlc: MagicMock) -> None:
    mock_vlc.get_time.side_effect = RuntimeError("libvlc boom")
    player = VLCPlayer()
    with pytest.raises(PlaybackError, match="position") as exc_info:
        player.get_position()
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_has_ended_true_for_ended_and_error_states(mock_vlc: MagicMock) -> None:
    mock_vlc.get_state.return_value = vlc.State.Ended
    player = VLCPlayer()
    assert player.has_ended() is True
    mock_vlc.get_state.return_value = vlc.State.Error
    assert player.has_ended() is True


def test_has_ended_false_when_playing(mock_vlc: MagicMock) -> None:
    mock_vlc.get_state.return_value = vlc.State.Playing
    player = VLCPlayer()
    assert player.has_ended() is False


def test_has_ended_wraps_vlc_errors_as_playback_error(mock_vlc: MagicMock) -> None:
    mock_vlc.get_state.side_effect = RuntimeError("libvlc boom")
    player = VLCPlayer()
    with pytest.raises(PlaybackError) as exc_info:
        player.has_ended()
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_init_wraps_vlc_errors_as_playback_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "ytmusic_cli.music.player.vlc.Instance",
        side_effect=OSError("no libvlc"),
    )
    with pytest.raises(PlaybackError, match="Failed to initialize") as exc_info:
        VLCPlayer()
    assert isinstance(exc_info.value.__cause__, OSError)
