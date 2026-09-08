"""Session identity gate shown before the player shell."""

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ytmusic_tui.consts import COMPACT_HEIGHT_ROWS, DEFAULT_USERNAME
from ytmusic_tui.exceptions import YTMusicError
from ytmusic_tui.music.types import StartupSettings, User
from ytmusic_tui.tui.access import ytmusic_app
from ytmusic_tui.tui.modals.prompt import PromptModal
from ytmusic_tui.tui.widgets.select_list import SelectList

WORDMARK_FULL = (
    "╦ ╦ ╔╦╗ ╔╦╗ ╦ ╦ ╔═╗ ═╦═ ╔═╗\n"
    "╚╦╝  ║  ║║║ ║ ║ ╚═╗  ║  ║  \n"
    " ╩   ╩  ╩ ╩ ╚═╝ ╚═╝ ═╩═ ╚═╝"
)
WORDMARK_COMPACT = "YTMUSIC"
WORDMARK_TUI = "T U I"


class WelcomeScreen(Screen[User | None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "new_profile", "New", show=False),
        Binding("q", "quit_welcome", "Quit", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome_column"):
            yield Static(WORDMARK_FULL, id="welcome_mark", markup=False)
            yield Static(WORDMARK_TUI, id="welcome_tui", markup=False)
            yield Static(
                "unofficial terminal player",
                id="welcome_tag",
                markup=False,
            )
            yield SelectList(id="welcome_profiles", markup=False)
            yield Label("No profiles. Press n to create one.", id="welcome_empty")
            yield Static(
                "enter select   n new   q quit",
                id="welcome_hints",
                markup=False,
            )

    def on_mount(self) -> None:
        self._apply_compact()
        self._pulse_mark()
        self.reload()

    def on_resize(self) -> None:
        self._apply_compact()

    def _apply_compact(self) -> None:
        compact = self.size.height < COMPACT_HEIGHT_ROWS
        self.query_one("#welcome_tag", Static).display = not compact
        mark = self.query_one("#welcome_mark", Static)
        mark.update(WORDMARK_COMPACT if compact else WORDMARK_FULL)

    def _pulse_mark(self) -> None:
        if not self.is_mounted:
            return
        mark = self.query_one("#welcome_mark", Static)
        mark.styles.animate(
            "opacity",
            0.65,
            duration=1.4,
            easing="in_out_cubic",
            on_complete=self._pulse_mark_restore,
        )

    def _pulse_mark_restore(self) -> None:
        if not self.is_mounted:
            return
        mark = self.query_one("#welcome_mark", Static)
        mark.styles.animate(
            "opacity",
            1.0,
            duration=1.4,
            easing="in_out_cubic",
            on_complete=self._pulse_mark,
        )

    @work(thread=True, exclusive=True, group="welcome")
    def reload(self) -> None:
        app = ytmusic_app(self.app)
        try:
            users = app.account_service.list_users()
            startup = app.account_service.get_startup()
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self._apply_users, users, startup)

    def _apply_users(self, users: list[User], startup: StartupSettings) -> None:
        option_list = self.query_one("#welcome_profiles", SelectList)
        option_list.clear_options()
        empty = self.query_one("#welcome_empty", Label)
        empty.display = not users
        option_list.display = bool(users)
        highlighted = _highlight_index(users, startup)
        for user in users:
            option_list.add_option(Option(user["username"], id=f"user_{user['id']}"))
        if users:
            option_list.highlighted = highlighted
            option_list.focus()

    def action_new_profile(self) -> None:
        self.app.push_screen(PromptModal("New profile", "Name"), self._on_new_name)

    def action_quit_welcome(self) -> None:
        self.dismiss(None)

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

    @work(thread=True, exclusive=True, group="welcome")
    def _select_profile(self, user_id: int) -> None:
        app = ytmusic_app(self.app)
        try:
            user = app.account_service.select_user(user_id)
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self.dismiss, user)

    @work(thread=True, exclusive=True, group="welcome")
    def _create_profile(self, name: str) -> None:
        app = ytmusic_app(self.app)
        try:
            user = app.account_service.create_user(name)
            app.account_service.select_user(user["id"])
        except YTMusicError as err:
            app.call_from_thread(self.notify, str(err), severity="error")
            return
        app.call_from_thread(self.dismiss, user)


def _highlight_index(users: list[User], startup: StartupSettings) -> int:
    default_id = startup["default_user_id"]
    local_index = 0
    for index, user in enumerate(users):
        if default_id is not None and user["id"] == default_id:
            return index
        if user["username"] == DEFAULT_USERNAME:
            local_index = index
    return local_index
