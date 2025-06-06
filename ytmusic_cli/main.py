"""Main entry point for YTMusic CLI application."""

import sys
from typing import Any, ClassVar

import click
from textual.app import App, ComposeResult
from textual.containers import Center
from textual.widgets import Footer

from ytmusic_cli.theme import ytmusic_theme
from ytmusic_cli.tui.ascii_title import AsciiTitle
from ytmusic_cli.tui.header import Header
from ytmusic_cli.tui.main_menu import MainMenu

from . import __version__


class YTMusicApp(App):
    """Main Textual application for YTMusic CLI."""

    TITLE = "YTMusic CLI"
    SUB_TITLE = "YouTube Music Terminal Interface"
    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
        ("a", "accounts", "Accounts"),
        ("p", "playlists", "Playlists"),
        ("s", "search", "Search"),
        ("h", "help", "Help"),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Register our custom theme
        self.register_theme(ytmusic_theme)
        # Set it as the default theme
        self.theme = "ytmusic"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Center(AsciiTitle(), id="ascii_title")
        yield MainMenu(id="main_menu")
        yield Footer()

    def action_search(self) -> None:
        """Open search interface."""
        self.bell()
        # TODO: Implement search functionality

    def action_playlists(self) -> None:
        """Show playlists."""
        self.bell()
        # TODO: Implement playlist functionality

    def action_help(self) -> None:
        """Show help."""
        self.bell()
        # TODO: Implement help screen


@click.command()
@click.version_option(version=__version__)
def main() -> None:
    """YTMusic CLI - A modern terminal interface for YouTube Music.

    Use arrow keys to navigate, Enter to select, and 'q' to quit.
    """

    try:
        app = YTMusicApp()
        app.run()
    except KeyboardInterrupt:
        click.echo("\nGoodbye! 🎵")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
