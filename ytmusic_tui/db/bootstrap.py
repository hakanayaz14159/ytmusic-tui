import logging

from peewee import OperationalError, SqliteDatabase

from ytmusic_tui.consts import APP_DIR, DB_PATH
from ytmusic_tui.db.app_config import AppConfig
from ytmusic_tui.db.db import db
from ytmusic_tui.db.playlist import Playlist
from ytmusic_tui.db.song import Song
from ytmusic_tui.db.user import User
from ytmusic_tui.exceptions import DatabaseError

logger = logging.getLogger(__name__)

_MODELS = [User, Song, Playlist, Playlist.songs.get_through_model(), AppConfig]


def ensure_app_config_columns(database: SqliteDatabase | None = None) -> None:
    connection = db if database is None else database
    table = AppConfig._meta.table_name
    columns = {column.name for column in connection.get_columns(table)}
    if "skip_keymap" in columns:
        return
    logger.info("adding appconfig.skip_keymap column")
    connection.execute_sql(
        f"ALTER TABLE {table} ADD COLUMN skip_keymap VARCHAR(8) NOT NULL DEFAULT 'auto'"
    )


def bootstrap() -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not DB_PATH.exists():
            DB_PATH.touch()
        if db.is_closed():
            db.connect(reuse_if_open=True)
        db.create_tables(_MODELS)
        ensure_app_config_columns()
    except (OperationalError, OSError) as err:
        logger.exception("database bootstrap failed")
        raise DatabaseError("database bootstrap failed") from err
