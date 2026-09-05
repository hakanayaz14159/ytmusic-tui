"""Settings mode: per-profile volume and search limit."""

from typing import TYPE_CHECKING, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ytmusic_cli.consts import MAX_SEARCH_LIMIT, MIN_SEARCH_LIMIT
from ytmusic_cli.exceptions import YTMusicError
from ytmusic_cli.tui.widgets.select_list import SelectList

if TYPE_CHECKING:
    from ytmusic_cli.main import YTMusicApp
    from ytmusic_cli.music.types import UserSettings

_VOLUME_STEP = 5
_LIMIT_STEP = 1


class SettingsMode(Vertical):
    DEFAULT_CSS = """
    SettingsMode {
        width: 1fr;
        height: 1fr;
        layout: vertical;
        overflow: hidden hidden;
    }
    """

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
            "default_volume": 80,
            "search_limit": 10,
        }

    def compose(self) -> ComposeResult:
        yield SelectList(id="settings_list")

    def reload(self) -> None:
        app = cast("YTMusicApp", self.app)
        if app.settings_service is not None:
            self._settings = app.settings_service.get()
        self._refresh_options()

    def activate(self) -> None:
        self.query_one("#settings_list", SelectList).focus()

    def action_save(self) -> None:
        app = cast("YTMusicApp", self.app)
        if app.settings_service is None:
            self.notify("Settings are unavailable", severity="warning")
            return
        try:
            self._settings = app.settings_service.save(self._settings)
        except YTMusicError as err:
            self.notify(str(err), severity="error")
            return
        self.notify("Settings saved", severity="information")
        self._refresh_options()

    def action_adjust_up(self) -> None:
        self._adjust(1)

    def action_adjust_down(self) -> None:
        self._adjust(-1)

    def _adjust(self, direction: int) -> None:
        option_list = self.query_one("#settings_list", SelectList)
        index = option_list.highlighted
        if index == 0:
            volume = self._settings["default_volume"] + direction * _VOLUME_STEP
            self._settings["default_volume"] = max(0, min(100, volume))
        elif index == 1:
            limit = self._settings["search_limit"] + direction * _LIMIT_STEP
            self._settings["search_limit"] = max(
                MIN_SEARCH_LIMIT,
                min(MAX_SEARCH_LIMIT, limit),
            )
        self._refresh_options()

    def on_option_list_option_selected(
        self,
        _event: OptionList.OptionSelected,
    ) -> None:
        self.action_adjust_up()

    def _refresh_options(self) -> None:
        option_list = self.query_one("#settings_list", SelectList)
        highlighted = option_list.highlighted
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
        if highlighted is not None:
            option_list.highlighted = highlighted
