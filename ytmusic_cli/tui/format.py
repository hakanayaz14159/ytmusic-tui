"""Terminal formatting helpers for durations, gauges, and song rows."""

from ytmusic_cli.consts import MAX_VOLUME
from ytmusic_cli.music.types import Song


def format_duration(seconds: float | int) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_progress_bar(position: float, duration: int, width: int = 16) -> str:
    if duration <= 0 or width <= 0:
        return "░" * max(0, width)
    ratio = min(1.0, max(0.0, position / float(duration)))
    filled = round(ratio * width)
    return f"{'█' * filled}{'░' * (width - filled)}"


def format_volume_gauge(volume: int, width: int = 6) -> str:
    clamped = max(0, min(MAX_VOLUME, volume))
    filled = round(clamped / MAX_VOLUME * width)
    return f"{'▮' * filled}{'▯' * (width - filled)}"


def format_song_line(song: Song, *, playing: bool = False) -> str:
    marker = "♫" if playing else " "
    title = _fit(song["title"], 36)
    artist = _fit(song["artist"] or "Unknown Artist", 22)
    return f"{marker} {title}  {artist}  {format_duration(song['duration'])}"


def _fit(text: str, width: int) -> str:
    if len(text) <= width:
        return text.ljust(width)
    if width <= 1:
        return text[:width]
    return f"{text[: width - 1]}…"
