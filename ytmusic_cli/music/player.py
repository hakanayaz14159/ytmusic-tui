"""VLC-backed audio player adapter."""

import logging

import vlc

from ytmusic_cli.exceptions import PlaybackError
from ytmusic_cli.music.types import AudioStream
from ytmusic_cli.utils.log import redact_url, vlc_log_file_path

logger = logging.getLogger(__name__)

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
            url = stream["url"]
            media = self._instance.media_new(url)

            headers = stream.get("http_headers") or {}
            applied: list[str] = []
            skipped: list[str] = []
            for name, value in headers.items():
                lowered = name.lower()
                if lowered in _SKIP_HTTP_HEADERS:
                    skipped.append(name)
                    continue
                if lowered == "user-agent":
                    media.add_option(f":http-user-agent={value}")
                elif lowered in ("referer", "referrer"):
                    media.add_option(f":http-referrer={value}")
                else:
                    media.add_option(f":http-extra-header={name}: {value}")
                applied.append(name)

            self._player.set_media(media)
            result = self._player.play()
            logger.info(
                "play url=%s applied=%s skipped=%s rc=%s",
                redact_url(url),
                applied,
                skipped,
                result,
            )
            if result == -1:
                logger.error("play rc=-1 url=%s", redact_url(url))
                raise PlaybackError(
                    f"Failed to play stream: {url} (libvlc returned -1)"
                )
        except PlaybackError:
            raise
        except Exception as err:
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
            return max(0.0, time_ms / 1000.0)
        except Exception as err:
            logger.exception("get_position failed")
            raise PlaybackError("Failed to get playback position") from err

    def has_ended(self) -> bool:
        try:
            return self._player.get_state() == vlc.State.Ended
        except Exception as err:
            logger.exception("has_ended failed")
            raise PlaybackError("Failed to query playback end state") from err

    def has_failed(self) -> bool:
        try:
            return self._player.get_state() == vlc.State.Error
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
