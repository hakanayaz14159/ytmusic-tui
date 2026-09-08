"""Profile and startup use cases."""

import logging

from ytmusic_tui.consts import DEFAULT_USERNAME
from ytmusic_tui.exceptions import ValidationError
from ytmusic_tui.music.ports import AppConfigRepositoryProtocol, UserRepositoryProtocol
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import PlaybackStatus, StartupSettings, User

logger = logging.getLogger(__name__)


class AccountService:
    """Local profile create / select / delete."""

    def __init__(
        self,
        users: UserRepositoryProtocol,
        state: AppState,
        config: AppConfigRepositoryProtocol,
    ) -> None:
        self._users = users
        self._state = state
        self._config = config

    def ensure_default_user(self) -> User:
        local = self._users.get_by_username(DEFAULT_USERNAME)
        if local is not None:
            return local
        existing = self._users.list_users()
        if len(existing) == 1:
            return existing[0]
        return self._users.create_user(DEFAULT_USERNAME)

    def list_users(self) -> list[User]:
        return self._users.list_users()

    def create_user(self, username: str) -> User:
        cleaned = username.strip()
        if not cleaned:
            logger.warning("profile create rejected empty name")
            raise ValidationError("Profile name must not be empty")
        user = self._users.create_user(cleaned)
        logger.info("profile created id=%s username=%s", user["id"], user["username"])
        return user

    def select_user(self, user_id: int) -> User:
        user = self._users.get_user(user_id)
        if user is None:
            logger.warning("profile select missing id=%s", user_id)
            raise ValidationError("Profile not found")
        logger.info("profile selected id=%s username=%s", user["id"], user["username"])
        current = self._state.current_user.get()
        if current is None or current["id"] != user_id:
            self._state.current_playlist.set(None)
        self._state.current_user.set(user)
        playback = self._state.playback_state.get()
        if playback["status"] == PlaybackStatus.STOPPED:
            self._state.playback_state.set(
                {**playback, "volume": user["default_volume"]}
            )
        return user

    def get_startup(self) -> StartupSettings:
        return self._config.get()

    def save_startup(self, settings: StartupSettings) -> StartupSettings:
        default_id = settings["default_user_id"]
        if default_id is not None and self._users.get_user(default_id) is None:
            logger.warning("startup save rejected missing id=%s", default_id)
            raise ValidationError("Profile not found")
        saved = self._config.save(
            {
                "skip_welcome": settings["skip_welcome"],
                "default_user_id": default_id,
            }
        )
        logger.info(
            "startup saved skip_welcome=%s default_user_id=%s",
            saved["skip_welcome"],
            saved["default_user_id"],
        )
        return saved

    def delete_user(self, user_id: int) -> None:
        users = self._users.list_users()
        if len(users) <= 1:
            logger.warning("profile delete rejected last id=%s", user_id)
            raise ValidationError("Cannot delete the last profile")
        logger.info("profile deleted id=%s", user_id)
        self._users.delete_user(user_id)
        startup = self._config.get()
        if startup["default_user_id"] == user_id:
            self._config.save({"skip_welcome": False, "default_user_id": None})
        current = self._state.current_user.get()
        if current is not None and current["id"] == user_id:
            remaining = self._users.list_users()
            self.select_user(remaining[0]["id"])
