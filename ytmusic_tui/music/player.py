"""VLC-backed audio player adapter."""

import logging
import sys
from typing import Protocol

from ytmusic_tui.exceptions import PlaybackError, VLCUnavailableError
from ytmusic_tui.music.stream_proxy import AudioStreamProxy
from ytmusic_tui.music.types import AudioStream
from ytmusic_tui.utils.log import redact_url, vlc_log_file_path

logger = logging.getLogger(__name__)

_VLC_LOAD_ERROR: OSError | NotImplementedError | None = None


class _VLCMedia(Protocol):
    """Opaque libvlc media handle."""


class _VLCState(Protocol):
    def __str__(self) -> str: ...


class _VLCMediaPlayer(Protocol):
    def set_media(self, media: _VLCMedia) -> None: ...

    def play(self) -> int: ...

    def pause(self) -> None: ...

    def stop(self) -> None: ...

    def is_playing(self) -> int: ...

    def audio_set_volume(self, volume: int) -> int: ...

    def audio_get_volume(self) -> int: ...

    def get_time(self) -> int: ...

    def set_time(self, time_ms: int) -> int: ...

    def get_state(self) -> _VLCState: ...


class _VLCInstance(Protocol):
    def media_player_new(self) -> _VLCMediaPlayer: ...

    def media_new(self, url: str) -> _VLCMedia: ...


class _VLCModule(Protocol):
    def Instance(self, *args: str) -> _VLCInstance: ...


vlc: _VLCModule | None
try:
    import vlc as _imported_vlc
except (OSError, NotImplementedError) as err:
    vlc = None
    _VLC_LOAD_ERROR = err
else:
    vlc = _imported_vlc
    _VLC_LOAD_ERROR = None


def _missing_vlc_message(platform: str | None = None) -> str:
    plat = sys.platform if platform is None else platform
    if plat == "darwin":
        install = "brew install --cask vlc"
    elif plat.startswith("win"):
        install = "install VLC from https://www.videolan.org/vlc/"
    else:
        install = "sudo apt install vlc  # or your distro's vlc package"
    return (
        "VLC is required for playback but was not found on this system.\n"
        f"Install it, then run ytmusic-tui again: {install}\n"
        "The VLC libraries cannot be installed from PyPI."
    )


def _require_vlc() -> _VLCModule:
    loaded = vlc
    if loaded is None:
        raise VLCUnavailableError(_missing_vlc_message()) from _VLC_LOAD_ERROR
    return loaded


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


def _vlc_version(lib: _VLCModule) -> str:
    getter = getattr(lib, "libvlc_get_version", None)
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
        libvlc = _require_vlc()
        try:
            args = _instance_args()
            logger.info("vlc init args=%s version=%s", args, _vlc_version(libvlc))
            self._instance = libvlc.Instance(*args)
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

    def seek(self, position: float) -> None:
        time_ms = int(max(0.0, position) * 1000.0)
        try:
            result = self._player.set_time(time_ms)
            logger.info("seek position=%s time_ms=%s rc=%s", position, time_ms, result)
            if result == -1:
                logger.error("seek rc=-1 position=%s", position)
                raise PlaybackError("Failed to seek")
        except PlaybackError:
            raise
        except Exception as err:
            logger.exception("seek failed position=%s", position)
            raise PlaybackError("Failed to seek") from err

    def has_ended(self) -> bool:
        try:
            return self._state_name() == "Ended"
        except Exception as err:
            logger.exception("has_ended failed")
            raise PlaybackError("Failed to query playback end state") from err

    def has_failed(self) -> bool:
        try:
            return self._state_name() == "Error"
        except Exception as err:
            logger.exception("has_failed failed")
            raise PlaybackError("Failed to query playback error state") from err

    def engine_state(self) -> str:
        try:
            return self._state_name()
        except Exception as err:
            logger.exception("engine_state failed")
            raise PlaybackError("Failed to query engine state") from err

    def _state_name(self) -> str:
        return str(self._player.get_state()).rsplit(".", 1)[-1]
