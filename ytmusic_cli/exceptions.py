"""Domain exception hierarchy for ytmusic-cli."""


class YTMusicError(Exception):
    """Base exception for all ytmusic-cli domain errors."""


class PlaybackError(YTMusicError):
    """Raised when audio playback or the player engine fails."""


class StreamExtractionError(YTMusicError):
    """Raised when stream URL or metadata extraction fails."""


class TrackNotFoundError(YTMusicError):
    """Raised when a requested track or video cannot be found."""


class DatabaseError(YTMusicError):
    """Raised when a persistence or relational constraint fails."""


class ValidationError(YTMusicError):
    """Raised when user input or domain validation fails."""
