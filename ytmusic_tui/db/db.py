import os

from peewee import Model, SqliteDatabase

from ytmusic_tui.consts import DB_NAME, DB_PATH

ENV = os.getenv("ENV", "production")

db = SqliteDatabase(DB_PATH if ENV == "production" else DB_NAME)


class BaseModel(Model):
    class Meta:
        database = db
