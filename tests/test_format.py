"""Table tests for duration, progress, and volume formatting."""

import pytest

from ytmusic_cli.tui.format import (
    format_duration,
    format_progress_bar,
    format_volume_gauge,
)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00"),
        (59, "00:59"),
        (60, "01:00"),
        (3600, "1:00:00"),
    ],
)
def test_format_duration(seconds: int, expected: str) -> None:
    assert format_duration(seconds) == expected


def test_format_progress_bar_clamps_and_empty() -> None:
    assert format_progress_bar(0, 0, width=4) == "░░░░"
    assert format_progress_bar(-10, 100, width=4) == "░░░░"
    assert format_progress_bar(200, 100, width=4) == "████"
    assert format_progress_bar(50, 100, width=4) == "██░░"


def test_format_volume_gauge_clamps() -> None:
    assert format_volume_gauge(-10, width=4) == "▯▯▯▯"
    assert format_volume_gauge(200, width=4) == "▮▮▮▮"
    assert format_volume_gauge(50, width=4) == "▮▮▯▯"
