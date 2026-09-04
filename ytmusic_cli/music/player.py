"""VLC-backed audio player adapter."""

import vlc

from ytmusic_cli.exceptions import PlaybackError
from ytmusic_cli.music.types import AudioStream


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
            user_agent = headers.get("User-Agent") or headers.get("user-agent")
            referrer = (
                headers.get("Referer")
                or headers.get("referer")
                or headers.get("Referrer")
                or headers.get("referrer")
            )
            if user_agent:
                media.add_option(f":http-user-agent={user_agent}")
            if referrer:
                media.add_option(f":http-referrer={referrer}")

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
