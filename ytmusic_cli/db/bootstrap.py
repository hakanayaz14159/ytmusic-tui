import logging

from ytmusic_cli.db.db import db
from ytmusic_cli.db.playlist import Playlist
from ytmusic_cli.db.repositories import UserRepository
from ytmusic_cli.db.song import Song
from ytmusic_cli.db.user import User
from ytmusic_cli.music.services import AccountService
from ytmusic_cli.music.state import AppState

logger = logging.getLogger(__name__)

_MODELS = [User, Song, Playlist, Playlist.songs.get_through_model()]


def bootstrap() -> None:
    try:
        if db.is_closed():
            db.connect(reuse_if_open=True)
        db.create_tables(_MODELS)
    except Exception:
        logger.exception("database bootstrap failed")
        raise
    account_service = AccountService(UserRepository(), AppState())
    user = account_service.ensure_default_user()
    account_service.select_user(user["id"])
