from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class MainMenu(Container):
    """A main menu widget."""

    def compose(self) -> ComposeResult:
        yield OptionList(
            Option("Select Account", id="select_account"),
            Option("Playlists", id="playlists"),
            Option("Search", id="search"),
            Option("Settings", id="settings"),
            Option("Help", id="help"),
            Option("Quit", id="quit"),
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle menu option selection."""
        option_id = event.option.id

        if option_id == "select_account":
            self.action_select_account()
        elif option_id == "playlists":
            self.action_playlists()
        elif option_id == "search":
            self.app.action_search()
        elif option_id == "settings":
            self.action_settings()
        elif option_id == "help":
            self.app.action_help()
        elif option_id == "quit":
            self.app.exit()

    def action_select_account(self) -> None:
        """Handle account selection."""
        self.app.bell()
        # TODO: Implement account selection functionality

    def action_playlists(self) -> None:
        """Handle playlists action."""
        self.app.action_playlists()

    def action_settings(self) -> None:
        """Handle settings action."""
        self.app.bell()
        # TODO: Implement settings functionality
