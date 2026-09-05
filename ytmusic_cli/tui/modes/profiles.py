"""Profiles mode: local listening identities."""

from typing import TYPE_CHECKING, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from ytmusic_cli.exceptions import YTMusicError
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import User
from ytmusic_cli.tui.modals.confirm import ConfirmModal
from ytmusic_cli.tui.modals.prompt import PromptModal
from ytmusic_cli.tui.widgets.select_list import SelectList

if TYPE_CHECKING:
    from ytmusic_cli.main import YTMusicApp


class ProfilesMode(Vertical):
    DEFAULT_CSS = """
    ProfilesMode {
        width: 1fr;
        height: 1fr;
        layout: vertical;
        overflow: hidden hidden;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "new_profile", "New", show=False),
        Binding("d", "delete_profile", "Delete", show=False),
    ]

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._users: list[User] = []

    def compose(self) -> ComposeResult:
        yield SelectList(id="profile_list")
        yield Label("No profiles available.", id="profiles_empty")

    def reload(self) -> None:
        app = cast("YTMusicApp", self.app)
        if app.account_service is None:
            self._users = []
            self._refresh_options()
            return
        self._users = app.account_service.list_users()
        self._refresh_options()

    def activate(self) -> None:
        self.query_one("#profile_list", SelectList).focus()

    def action_new_profile(self) -> None:
        self.app.push_screen(PromptModal("New profile", "Name"), self._on_new_name)

    def action_delete_profile(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        self.app.push_screen(
            ConfirmModal(f"Delete profile “{user['username']}”?"),
            self._on_confirm_delete,
        )

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        if event.option.id is None:
            return
        user_id = int(event.option.id.removeprefix("user_"))
        app = cast("YTMusicApp", self.app)
        if app.account_service is None:
            return
        try:
            user = app.account_service.select_user(user_id)
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        self.notify(f"Switched to {user['username']}", severity="information")
        self.reload()

    def _on_new_name(self, name: str | None) -> None:
        if name is None:
            return
        app = cast("YTMusicApp", self.app)
        if app.account_service is None:
            return
        try:
            user = app.account_service.create_user(name)
            app.account_service.select_user(user["id"])
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        self.reload()
        self.notify(f"Created {user['username']}", severity="information")

    def _on_confirm_delete(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        user = self._selected_user()
        app = cast("YTMusicApp", self.app)
        if user is None or app.account_service is None:
            return
        try:
            app.account_service.delete_user(user["id"])
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        self.reload()

    def _selected_user(self) -> User | None:
        option_list = self.query_one("#profile_list", SelectList)
        highlighted = option_list.highlighted
        if highlighted is None or highlighted >= len(self._users):
            return None
        return self._users[highlighted]

    def _refresh_options(self) -> None:
        option_list = self.query_one("#profile_list", SelectList)
        option_list.clear_options()
        empty = self.query_one("#profiles_empty", Label)
        empty.display = not self._users
        current = AppState().current_user.get()
        current_id = current["id"] if current is not None else None
        for user in self._users:
            marker = "• " if user["id"] == current_id else "  "
            option_list.add_option(
                Option(f"{marker}{user['username']}", id=f"user_{user['id']}")
            )
