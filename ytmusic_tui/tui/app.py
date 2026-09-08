"""Typed accessor for the running player app."""

from typing import TYPE_CHECKING, cast

from textual.app import App

if TYPE_CHECKING:
    from ytmusic_tui.main import YTMusicApp


def ytmusic_app(app: App[object]) -> "YTMusicApp":
    return cast("YTMusicApp", app)
