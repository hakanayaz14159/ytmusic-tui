"""Per-user settings use cases."""

import logging

from ytmusic_tui.consts import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_VOLUME,
    MAX_SEARCH_LIMIT,
    MAX_VOLUME,
    MIN_SEARCH_LIMIT,
)
from ytmusic_tui.exceptions import ValidationError
from ytmusic_tui.music.ports import UserRepositoryProtocol
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import UserSettings

logger = logging.getLogger(__name__)


class SettingsService:
    """Per-user default volume and search result limit."""

    def __init__(
        self,
        users: UserRepositoryProtocol,
        state: AppState,
    ) -> None:
        self._users = users
        self._state = state

    def get(self) -> UserSettings:
        user = self._state.current_user.get()
        if user is None:
            return {
                "default_volume": DEFAULT_VOLUME,
                "search_limit": DEFAULT_SEARCH_LIMIT,
            }
        return {
            "default_volume": user["default_volume"],
            "search_limit": user["search_limit"],
        }

    def save(self, settings: UserSettings) -> UserSettings:
        volume = settings["default_volume"]
        limit = settings["search_limit"]
        if volume < 0 or volume > MAX_VOLUME:
            logger.warning("settings save rejected volume=%s", volume)
            raise ValidationError(f"Volume must be between 0 and {MAX_VOLUME}")
        if limit < MIN_SEARCH_LIMIT or limit > MAX_SEARCH_LIMIT:
            logger.warning("settings save rejected search_limit=%s", limit)
            raise ValidationError(
                f"Search limit must be between {MIN_SEARCH_LIMIT} "
                f"and {MAX_SEARCH_LIMIT}"
            )
        user = self._state.current_user.get()
        if user is None:
            logger.warning("settings save rejected no profile")
            raise ValidationError("No profile selected")
        updated = self._users.update_settings(
            user["id"],
            {"default_volume": volume, "search_limit": limit},
        )
        current = self._state.current_user.get()
        if current is not None and current["id"] == updated["id"]:
            self._state.current_user.set(updated)
        logger.info(
            "settings saved volume=%s search_limit=%s",
            updated["default_volume"],
            updated["search_limit"],
        )
        return {
            "default_volume": updated["default_volume"],
            "search_limit": updated["search_limit"],
        }
