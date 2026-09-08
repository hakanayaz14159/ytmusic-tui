"""Tests for ISO/ANSI skip-key detection and resolution."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from ytmusic_tui.music.types import SkipKeymap, SkipKeymapMode
from ytmusic_tui.tui.skip_keymap import (
    _read_localectl_status,
    detect_skip_keymap,
    parse_localectl_x11_model,
    parse_xkb_model,
    resolve_skip_keymap,
    skip_keymap_label,
)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("pc105", SkipKeymap.ISO),
        ("pc105+inet", SkipKeymap.ISO),
        ("pc102", SkipKeymap.ISO),
        ("pc105iso", SkipKeymap.ISO),
        ("macintosh_iso", SkipKeymap.ISO),
        ("pc104", SkipKeymap.ANSI),
        ("pc101", SkipKeymap.ANSI),
        ("macintosh", SkipKeymap.ANSI),
        ("", None),
        ("   ", None),
        ("pc99", None),
        ("unknown", None),
    ],
)
def test_parse_xkb_model(model: str, expected: SkipKeymap | None) -> None:
    assert parse_xkb_model(model) == expected


def test_parse_localectl_x11_model_reads_pc105() -> None:
    status = (
        "   System Locale: LANG=en_US.UTF-8\n"
        "       VC Keymap: us\n"
        "      X11 Layout: us\n"
        "       X11 Model: pc105\n"
    )
    assert parse_localectl_x11_model(status) == "pc105"


def test_parse_localectl_x11_model_missing_returns_none() -> None:
    assert parse_localectl_x11_model("VC Keymap: us\n") is None


def test_parse_localectl_x11_model_blank_value_returns_none() -> None:
    assert parse_localectl_x11_model("X11 Model:   \n") is None


@pytest.mark.parametrize(
    ("mode", "detected", "expected"),
    [
        (SkipKeymapMode.ISO, SkipKeymap.ANSI, SkipKeymap.ISO),
        (SkipKeymapMode.ANSI, SkipKeymap.ISO, SkipKeymap.ANSI),
        (SkipKeymapMode.AUTO, SkipKeymap.ANSI, SkipKeymap.ANSI),
        (SkipKeymapMode.AUTO, SkipKeymap.ISO, SkipKeymap.ISO),
        (SkipKeymapMode.AUTO, None, SkipKeymap.ISO),
    ],
)
def test_resolve_skip_keymap(
    mode: SkipKeymapMode,
    detected: SkipKeymap | None,
    expected: SkipKeymap,
) -> None:
    assert resolve_skip_keymap(mode, detected) == expected


def test_skip_keymap_label_auto_uses_resolved_geometry() -> None:
    assert skip_keymap_label(SkipKeymapMode.AUTO, None) == "auto (ISO)"
    assert skip_keymap_label(SkipKeymapMode.AUTO, SkipKeymap.ANSI) == "auto (US)"
    assert skip_keymap_label(SkipKeymapMode.ISO, None) == "ISO (< z)"
    assert skip_keymap_label(SkipKeymapMode.ANSI, None) == "US (z x)"


def test_detect_skip_keymap_uses_x11_model(mocker: MockerFixture) -> None:
    mocker.patch(
        "ytmusic_tui.tui.skip_keymap._read_localectl_status",
        return_value="       X11 Model: pc104\n",
    )
    assert detect_skip_keymap() is SkipKeymap.ANSI


def test_detect_skip_keymap_none_when_localectl_missing(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "ytmusic_tui.tui.skip_keymap._read_localectl_status",
        return_value=None,
    )
    assert detect_skip_keymap() is None


def test_read_localectl_status_swallows_missing_binary(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "ytmusic_tui.tui.skip_keymap.subprocess.run",
        side_effect=FileNotFoundError("localectl"),
    )
    assert _read_localectl_status() is None


def test_read_localectl_status_swallows_nonzero(
    mocker: MockerFixture,
) -> None:
    completed = MagicMock()
    completed.returncode = 1
    completed.stdout = ""
    mocker.patch("ytmusic_tui.tui.skip_keymap.subprocess.run", return_value=completed)
    assert _read_localectl_status() is None
