"""Settings mode: per-profile volume and app startup policy."""

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ytmusic_tui.consts import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_VOLUME,
    MAX_SEARCH_LIMIT,
    MAX_VOLUME,
    MIN_SEARCH_LIMIT,
)
from ytmusic_tui.exceptions import YTMusicError
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import StartupSettings, User, UserSettings
from ytmusic_tui.tui.app import ytmusic_app
from ytmusic_tui.tui.widgets.select_list import SelectList

_VOLUME_STEP = 5
_LIMIT_STEP = 1


class SettingsMode(Vertical):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("s", "save", "Save", show=False),
        Binding("left", "adjust_down", show=False),
        Binding("right", "adjust_up", show=False),
        Binding("h", "adjust_down", show=False),
        Binding("l", "adjust_up", show=False),
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
        self._settings: UserSettings = {
            "default_volume": DEFAULT_VOLUME,
            "search_limit": DEFAULT_SEARCH_LIMIT,
        }
        self._startup: StartupSettings = {
            "skip_welcome": False,
            "default_user_id": None,
        }
        self._users: list[User] = []
        self._hydrated = False

    def compose(self) -> ComposeResult:
        yield SelectList(id="settings_list", markup=False)

    def reload(self) -> None:
        self._hydrated = False
        self._load()

    @work(thread=True, exclusive=True, group="settings-load")
    def _load(self) -> None:
        app = ytmusic_app(self.app)
        try:
            settings = app.settings_service.get()
            startup = app.account_service.get_startup()
            users = app.account_service.list_users()
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._apply, settings, startup, users)

    def _apply(
        self,
        settings: UserSettings,
        startup: StartupSettings,
        users: list[User],
    ) -> None:
        self._settings = settings
        self._startup = {
            "skip_welcome": startup["skip_welcome"],
            "default_user_id": startup["default_user_id"],
        }
        self._users = users
        if self._startup["default_user_id"] is None and self._users:
            current = AppState().current_user.get()
            if current is not None:
                self._startup["default_user_id"] = current["id"]
            else:
                self._startup["default_user_id"] = self._users[0]["id"]
        self._hydrated = True
        self._refresh_options()

    def activate(self) -> None:
        self.query_one("#settings_list", SelectList).focus()

    @work(thread=True, exclusive=True, group="settings-save")
    def action_save(self) -> None:
        app = ytmusic_app(self.app)
        if not self._hydrated:
            app.call_from_thread(
                self.notify,
                "Settings are still loading",
                severity="warning",
            )
            return
        try:
            saved = app.settings_service.save(self._settings)
            startup = app.account_service.save_startup(self._startup)
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._on_saved, saved, startup)

    def _on_saved(self, settings: UserSettings, startup: StartupSettings) -> None:
        self._settings = settings
        self._startup = startup
        self.notify("Settings saved", severity="information")
        self._refresh_options()

    def action_adjust_up(self) -> None:
        self._adjust(1)

    def action_adjust_down(self) -> None:
        self._adjust(-1)

    def _adjust(self, direction: int) -> None:
        option_list = self.query_one("#settings_list", SelectList)
        index = option_list.highlighted
        if index is None:
            return
        option_id = option_list.get_option_at_index(index).id
        if option_id == "vol":
            volume = self._settings["default_volume"] + direction * _VOLUME_STEP
            self._settings["default_volume"] = max(0, min(MAX_VOLUME, volume))
        elif option_id == "limit":
            limit = self._settings["search_limit"] + direction * _LIMIT_STEP
            self._settings["search_limit"] = max(
                MIN_SEARCH_LIMIT,
                min(MAX_SEARCH_LIMIT, limit),
            )
        elif option_id == "skip_welcome":
            self._startup["skip_welcome"] = not self._startup["skip_welcome"]
        elif option_id == "startup_profile":
            self._cycle_startup_profile(direction)
        self._refresh_options()

    def _cycle_startup_profile(self, direction: int) -> None:
        if not self._users:
            return
        ids = [user["id"] for user in self._users]
        current = self._startup["default_user_id"]
        index = 0 if current not in ids else ids.index(current)
        self._startup["default_user_id"] = ids[(index + direction) % len(ids)]

    def on_option_list_option_selected(
        self,
        _event: OptionList.OptionSelected,
    ) -> None:
        self.action_adjust_up()

    def _refresh_options(self) -> None:
        option_list = self.query_one("#settings_list", SelectList)
        highlighted = option_list.highlighted
        screen = "skip" if self._startup["skip_welcome"] else "show"
        profile = _startup_username(self._users, self._startup["default_user_id"])
        option_list.clear_options()
        option_list.add_option(
            Option(f"Default volume    {self._settings['default_volume']}%", id="vol")
        )
        option_list.add_option(
            Option(
                f"Search results    {self._settings['search_limit']}",
                id="limit",
            )
        )
        option_list.add_option(Option(f"Profile screen    {screen}", id="skip_welcome"))
        option_list.add_option(
            Option(f"Startup profile   {profile}", id="startup_profile")
        )
        option_list.highlighted = 0 if highlighted is None else highlighted


def _startup_username(users: list[User], user_id: int | None) -> str:
    if user_id is None:
        return "—"
    for user in users:
        if user["id"] == user_id:
            return user["username"]
    return "—"
