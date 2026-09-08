import logging

from peewee import OperationalError

from ytmusic_tui.consts import APP_DIR, DB_PATH
from ytmusic_tui.db.db import db
from ytmusic_tui.db.playlist import Playlist
from ytmusic_tui.db.repositories import UserRepository
from ytmusic_tui.db.song import Song
from ytmusic_tui.db.user import User
from ytmusic_tui.exceptions import DatabaseError
from ytmusic_tui.music.services import AccountService
from ytmusic_tui.music.state import AppState

logger = logging.getLogger(__name__)

_MODELS = [User, Song, Playlist, Playlist.songs.get_through_model()]


def bootstrap() -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not DB_PATH.exists():
            DB_PATH.touch()
        if db.is_closed():
            db.connect(reuse_if_open=True)
        db.create_tables(_MODELS)
    except (OperationalError, OSError) as err:
        logger.exception("database bootstrap failed")
        raise DatabaseError("database bootstrap failed") from err
    account_service = AccountService(UserRepository(), AppState())
    user = account_service.ensure_default_user()
    account_service.select_user(user["id"])
