"""Resolve ISO vs ANSI queue-skip keys from settings and XKB geometry."""

import logging
import subprocess

from ytmusic_tui.music.types import SkipKeymap, SkipKeymapMode

logger = logging.getLogger(__name__)

_LOCALECTL_TIMEOUT = 2.0


def parse_xkb_model(model: str) -> SkipKeymap | None:
    normalized = model.strip().lower()
    if not normalized:
        return None
    if "iso" in normalized or "pc105" in normalized or "pc102" in normalized:
        return SkipKeymap.ISO
    if "pc104" in normalized or "pc101" in normalized:
        return SkipKeymap.ANSI
    if "macintosh" in normalized:
        return SkipKeymap.ANSI
    return None


def parse_localectl_x11_model(status: str) -> str | None:
    for line in status.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("x11 model:"):
            model = stripped.split(":", 1)[1].strip()
            return model or None
    return None


def resolve_skip_keymap(
    mode: SkipKeymapMode,
    detected: SkipKeymap | None,
) -> SkipKeymap:
    if mode is SkipKeymapMode.ISO:
        return SkipKeymap.ISO
    if mode is SkipKeymapMode.ANSI:
        return SkipKeymap.ANSI
    if mode is SkipKeymapMode.AUTO:
        return detected if detected is not None else SkipKeymap.ISO
    raise ValueError(f"unknown skip keymap mode: {mode}")


def skip_keymap_label(mode: SkipKeymapMode, detected: SkipKeymap | None) -> str:
    if mode is SkipKeymapMode.ISO:
        return "ISO (< z)"
    if mode is SkipKeymapMode.ANSI:
        return "US (z x)"
    if mode is SkipKeymapMode.AUTO:
        resolved = resolve_skip_keymap(mode, detected)
        geometry = "ISO" if resolved is SkipKeymap.ISO else "US"
        return f"auto ({geometry})"
    raise ValueError(f"unknown skip keymap mode: {mode}")


def detect_skip_keymap() -> SkipKeymap | None:
    status = _read_localectl_status()
    if status is None:
        return None
    model = parse_localectl_x11_model(status)
    if model is None:
        return None
    return parse_xkb_model(model)


def _read_localectl_status() -> str | None:
    try:
        result = subprocess.run(
            ["localectl", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=_LOCALECTL_TIMEOUT,
        )
    except (OSError, TimeoutError) as err:
        logger.info("localectl status unavailable: %s", err)
        return None
    if result.returncode != 0:
        logger.info("localectl status rc=%s", result.returncode)
        return None
    return result.stdout
