"""VLC-backed audio player adapter."""

import vlc

from ytmusic_cli.exceptions import PlaybackError


class VLCPlayer:
    """AudioPlayerProtocol implementation using python-vlc / libvlc."""

    def __init__(self) -> None:
        try:
            self._instance = vlc.Instance()
            self._player = self._instance.media_player_new()
        except Exception as err:
            raise PlaybackError("Failed to initialize VLC player") from err

    def play(self, url: str) -> None:
        try:
            media = self._instance.media_new(url)
            self._player.set_media(media)
            self._player.play()
        except Exception as err:
            raise PlaybackError(f"Failed to play URL: {url}") from err

    def pause(self) -> None:
        try:
            self._player.pause()
        except Exception as err:
            raise PlaybackError("Failed to pause playback") from err

    def stop(self) -> None:
        try:
            self._player.stop()
        except Exception as err:
            raise PlaybackError("Failed to stop playback") from err

    def is_playing(self) -> bool:
        try:
            return bool(self._player.is_playing())
        except Exception as err:
            raise PlaybackError("Failed to query playback status") from err

    def set_volume(self, volume: int) -> None:
        clamped = max(0, min(100, volume))
        try:
            self._player.audio_set_volume(clamped)
        except Exception as err:
            raise PlaybackError(f"Failed to set volume to {clamped}") from err

    def get_volume(self) -> int:
        try:
            return int(self._player.audio_get_volume())
        except Exception as err:
            raise PlaybackError("Failed to get volume") from err
