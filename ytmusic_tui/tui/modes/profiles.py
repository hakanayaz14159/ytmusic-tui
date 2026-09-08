"""Profiles mode: local listening identities."""

from functools import partial
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from ytmusic_tui.exceptions import YTMusicError
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import User
from ytmusic_tui.tui.app import ytmusic_app
from ytmusic_tui.tui.modals.confirm import ConfirmModal
from ytmusic_tui.tui.modals.prompt import PromptModal
from ytmusic_tui.tui.widgets.select_list import SelectList


class ProfilesMode(Vertical):
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
        yield SelectList(id="profile_list", markup=False)
        yield Label("No profiles. Press n to create one.", id="profiles_empty")

    @work(thread=True, exclusive=True, group="profiles")
    def reload(self) -> None:
        app = ytmusic_app(self.app)
        try:
            users = app.account_service.list_users()
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._apply_users, users)

    def _apply_users(self, users: list[User]) -> None:
        self._users = users
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
            partial(self._on_confirm_delete, user),
        )

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        if event.option.id is None:
            return
        user_id = int(event.option.id.removeprefix("user_"))
        self._select_profile(user_id)

    def _on_new_name(self, name: str | None) -> None:
        if name is None:
            return
        self._create_profile(name)

    def _on_confirm_delete(self, user: User, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self._delete_profile(user)

    @work(thread=True, exclusive=True, group="profiles")
    def _select_profile(self, user_id: int) -> None:
        app = ytmusic_app(self.app)
        try:
            user = app.account_service.select_user(user_id)
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._on_profile_selected, user)

    def _on_profile_selected(self, user: User) -> None:
        self.notify(f"Switched to {user['username']}", severity="information")
        self.reload()

    @work(thread=True, exclusive=True, group="profiles")
    def _create_profile(self, name: str) -> None:
        app = ytmusic_app(self.app)
        try:
            user = app.account_service.create_user(name)
            app.account_service.select_user(user["id"])
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._on_profile_created, user)

    def _on_profile_created(self, user: User) -> None:
        self.reload()
        self.notify(f"Created {user['username']}", severity="information")

    @work(thread=True, exclusive=True, group="profiles")
    def _delete_profile(self, user: User) -> None:
        app = ytmusic_app(self.app)
        try:
            app.account_service.delete_user(user["id"])
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._on_profile_deleted, user)

    def _on_profile_deleted(self, user: User) -> None:
        self.reload()
        self.notify(f"Deleted {user['username']}", severity="information")

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
        highlighted = 0
        for index, user in enumerate(self._users):
            marker = "• " if user["id"] == current_id else "  "
            option_list.add_option(
                Option(f"{marker}{user['username']}", id=f"user_{user['id']}")
            )
            if user["id"] == current_id:
                highlighted = index
        if self._users:
            option_list.highlighted = highlighted
