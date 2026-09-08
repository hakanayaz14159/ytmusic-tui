"""VLC-backed audio player adapter."""

import logging

import vlc

from ytmusic_tui.exceptions import PlaybackError
from ytmusic_tui.music.stream_proxy import AudioStreamProxy
from ytmusic_tui.music.types import AudioStream
from ytmusic_tui.utils.log import redact_url, vlc_log_file_path

logger = logging.getLogger(__name__)


def _instance_args() -> list[str]:
    args = ["--no-video"]
    vlc_log = vlc_log_file_path()
    if vlc_log is None:
        args.append("--quiet")
        return args
    args.extend(
        [
            "--verbose=2",
            "--file-logging",
            f"--logfile={vlc_log}",
        ]
    )
    return args


def _vlc_version() -> str:
    getter = getattr(vlc, "libvlc_get_version", None)
    if getter is None:
        return "unknown"
    raw = getter()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


class VLCPlayer:
    """AudioPlayerProtocol implementation using python-vlc / libvlc."""

    def __init__(self) -> None:
        self._proxy = AudioStreamProxy()
        try:
            args = _instance_args()
            logger.info("vlc init args=%s version=%s", args, _vlc_version())
            self._instance = vlc.Instance(*args)
            self._player = self._instance.media_player_new()
        except Exception as err:
            logger.exception("vlc init failed")
            raise PlaybackError("Failed to initialize VLC player") from err

    def play(self, stream: AudioStream) -> None:
        try:
            local_url = self._proxy.start(stream)
            media = self._instance.media_new(local_url)
            self._player.set_media(media)
            result = self._player.play()
            logger.info(
                "play url=%s via=%s rc=%s",
                redact_url(stream["url"]),
                local_url,
                result,
            )
            if result == -1:
                logger.error("play rc=-1 url=%s", redact_url(stream["url"]))
                raise PlaybackError(
                    f"Failed to play stream: {stream['url']} (libvlc returned -1)"
                )
        except PlaybackError:
            self._proxy.stop()
            raise
        except Exception as err:
            self._proxy.stop()
            logger.exception("play failed url=%s", redact_url(stream.get("url", "")))
            raise PlaybackError(f"Failed to play URL: {stream.get('url', '')}") from err

    def pause(self) -> None:
        try:
            logger.info("pause")
            self._player.pause()
        except Exception as err:
            logger.exception("pause failed")
            raise PlaybackError("Failed to pause playback") from err

    def stop(self) -> None:
        try:
            logger.info("stop")
            self._player.stop()
        except Exception as err:
            logger.exception("stop failed")
            raise PlaybackError("Failed to stop playback") from err
        finally:
            self._proxy.stop()

    def is_playing(self) -> bool:
        try:
            return bool(self._player.is_playing())
        except Exception as err:
            logger.exception("is_playing failed")
            raise PlaybackError("Failed to query playback status") from err

    def set_volume(self, volume: int) -> None:
        clamped = max(0, min(100, volume))
        try:
            self._player.audio_set_volume(clamped)
        except Exception as err:
            logger.exception("set_volume failed volume=%s", clamped)
            raise PlaybackError(f"Failed to set volume to {clamped}") from err

    def get_volume(self) -> int:
        try:
            return int(self._player.audio_get_volume())
        except Exception as err:
            logger.exception("get_volume failed")
            raise PlaybackError("Failed to get volume") from err

    def get_position(self) -> float:
        try:
            time_ms = self._player.get_time()
            return max(0.0, float(time_ms) / 1000.0)
        except Exception as err:
            logger.exception("get_position failed")
            raise PlaybackError("Failed to get playback position") from err

    def has_ended(self) -> bool:
        try:
            return bool(self._player.get_state() == vlc.State.Ended)
        except Exception as err:
            logger.exception("has_ended failed")
            raise PlaybackError("Failed to query playback end state") from err

    def has_failed(self) -> bool:
        try:
            return bool(self._player.get_state() == vlc.State.Error)
        except Exception as err:
            logger.exception("has_failed failed")
            raise PlaybackError("Failed to query playback error state") from err

    def engine_state(self) -> str:
        try:
            state = self._player.get_state()
            return str(state).rsplit(".", 1)[-1]
        except Exception as err:
            logger.exception("engine_state failed")
            raise PlaybackError("Failed to query engine state") from err
