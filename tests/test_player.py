"""Tests for VLCPlayer audio adapter (mocked VLC, no hardware)."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from ytmusic_cli.exceptions import PlaybackError
from ytmusic_cli.music.player import VLCPlayer
from ytmusic_cli.music.ports import AudioPlayerProtocol


@pytest.fixture
def mock_vlc(mocker: MockerFixture) -> MagicMock:
    """Patch vlc.Instance and return the mock media player."""
    mock_instance = mocker.MagicMock()
    mock_media_player = mocker.MagicMock()
    mock_media = mocker.MagicMock()
    mock_instance.media_player_new.return_value = mock_media_player
    mock_instance.media_new.return_value = mock_media
    mocker.patch("ytmusic_cli.music.player.vlc.Instance", return_value=mock_instance)
    return mock_media_player


def test_vlc_player_implements_audio_player_protocol(mock_vlc: MagicMock) -> None:
    player = VLCPlayer()
    assert isinstance(player, AudioPlayerProtocol)
    assert mock_vlc is player._player


def test_play_sets_media_and_plays(mock_vlc: MagicMock) -> None:
    player = VLCPlayer()
    player.play("https://stream.example.com/audio.m4a")
    player._instance.media_new.assert_called_once_with(
        "https://stream.example.com/audio.m4a"
    )
    mock_vlc.set_media.assert_called_once()
    mock_vlc.play.assert_called_once()


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
    with pytest.raises(PlaybackError, match="Failed to play") as exc_info:
        player.play("https://stream.example.com/audio.m4a")
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_init_wraps_vlc_errors_as_playback_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "ytmusic_cli.music.player.vlc.Instance",
        side_effect=OSError("no libvlc"),
    )
    with pytest.raises(PlaybackError, match="Failed to initialize") as exc_info:
        VLCPlayer()
    assert isinstance(exc_info.value.__cause__, OSError)
