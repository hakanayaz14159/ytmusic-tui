"""VLC-backed audio player adapter."""

import vlc

from ytmusic_cli.exceptions import PlaybackError
from ytmusic_cli.music.types import AudioStream

_SKIP_HTTP_HEADERS = frozenset(
    {
        "accept-encoding",
        "content-encoding",
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "host",
        "content-length",
    }
)


class VLCPlayer:
    """AudioPlayerProtocol implementation using python-vlc / libvlc."""

    def __init__(self) -> None:
        try:
            self._instance = vlc.Instance("--no-video", "--quiet")
            self._player = self._instance.media_player_new()
        except Exception as err:
            raise PlaybackError("Failed to initialize VLC player") from err

    def play(self, stream: AudioStream) -> None:
        try:
            url = stream["url"]
            media = self._instance.media_new(url)

            headers = stream.get("http_headers") or {}
            for name, value in headers.items():
                lowered = name.lower()
                if lowered in _SKIP_HTTP_HEADERS:
                    continue
                if lowered == "user-agent":
                    media.add_option(f":http-user-agent={value}")
                elif lowered in ("referer", "referrer"):
                    media.add_option(f":http-referrer={value}")
                else:
                    media.add_option(f":http-extra-header={name}: {value}")

            self._player.set_media(media)
            result = self._player.play()
            if result == -1:
                raise PlaybackError(
                    f"Failed to play stream: {url} (libvlc returned -1)"
                )
        except PlaybackError:
            raise
        except Exception as err:
            raise PlaybackError(f"Failed to play URL: {stream.get('url', '')}") from err

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

    def get_position(self) -> float:
        try:
            time_ms = self._player.get_time()
            return max(0.0, time_ms / 1000.0)
        except Exception as err:
            raise PlaybackError("Failed to get playback position") from err

    def has_ended(self) -> bool:
        try:
            return self._player.get_state() == vlc.State.Ended
        except Exception as err:
            raise PlaybackError("Failed to query playback end state") from err

    def has_failed(self) -> bool:
        try:
            return self._player.get_state() == vlc.State.Error
        except Exception as err:
            raise PlaybackError("Failed to query playback error state") from err
