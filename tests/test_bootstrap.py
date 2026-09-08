"""Schema bootstrap helpers."""

from peewee import SqliteDatabase

from ytmusic_tui.db.app_config import AppConfig
from ytmusic_tui.db.bootstrap import ensure_app_config_columns


def test_ensure_app_config_columns_adds_missing_skip_keymap() -> None:
    database = SqliteDatabase(":memory:")
    database.connect()
    try:
        database.execute_sql(
            "CREATE TABLE appconfig ("
            "id INTEGER PRIMARY KEY, "
            "skip_welcome INTEGER NOT NULL, "
            "default_user_id INTEGER)"
        )
        columns = {column.name for column in database.get_columns("appconfig")}
        assert "skip_keymap" not in columns

        ensure_app_config_columns(database)

        columns = {column.name for column in database.get_columns("appconfig")}
        assert "skip_keymap" in columns
        ensure_app_config_columns(database)
        assert AppConfig._meta.table_name == "appconfig"
    finally:
        database.close()
