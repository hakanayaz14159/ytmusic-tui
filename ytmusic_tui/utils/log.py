"""File logging for ytmusic-tui. Enabled only when YTMUSIC_LOG=1."""

import logging
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from ytmusic_tui.consts import APP_DIR, LOG_ENV, LOG_FILE_ENV, LOG_LEVEL_ENV

LOGGER_NAME = "ytmusic_tui"
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_REDACT_HEADER_NAMES = frozenset({"cookie", "authorization"})

_log_state: dict[str, Path | None] = {"path": None}


def reset_logging() -> None:
    _log_state["path"] = None
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    logger.setLevel(logging.INFO)


def configure_logging(started_at: datetime | None = None) -> Path | None:
    reset_logging()
    if os.environ.get(LOG_ENV) != "1":
        return None
    path = _resolve_log_path(started_at or datetime.now())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger = logging.getLogger(LOGGER_NAME)
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
        existing.close()
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(_resolve_level())
    _log_state["path"] = path
    return path


def log_file_path() -> Path | None:
    return _log_state["path"]


def vlc_log_file_path() -> Path | None:
    path = _log_state["path"]
    if path is None:
        return None
    return path.with_name(f"{path.stem}.vlc.log")


def redact_url(url: str) -> str:
    return url.split("?", 1)[0]


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() in _REDACT_HEADER_NAMES:
            redacted[name] = "redacted"
        else:
            redacted[name] = value
    return redacted


def _resolve_log_path(started_at: datetime) -> Path:
    override = os.environ.get(LOG_FILE_ENV)
    if override:
        return Path(override).expanduser()
    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    return APP_DIR / f"ytmusic-{stamp}.log"


def _resolve_level() -> int:
    raw = os.environ.get(LOG_LEVEL_ENV, "INFO").upper()
    names = logging.getLevelNamesMapping()
    return names.get(raw, logging.INFO)


reset_logging()
