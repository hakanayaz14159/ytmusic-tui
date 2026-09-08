"""Typed accessor for the running YTMusicApp."""

from typing import TYPE_CHECKING

from textual.app import App

if TYPE_CHECKING:
    from ytmusic_tui.tui.app import YTMusicApp


def ytmusic_app(app: App[object]) -> "YTMusicApp":
    # Lazy: tui.app imports the shell, modes, and welcome, which import this.
    from ytmusic_tui.tui.app import YTMusicApp  # noqa: PLC0415

    if not isinstance(app, YTMusicApp):
        raise TypeError("expected YTMusicApp")
    return app
