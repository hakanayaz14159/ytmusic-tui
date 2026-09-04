from peewee import IntegerField, TextField

from ytmusic_cli.consts import DEFAULT_SEARCH_LIMIT, DEFAULT_VOLUME
from ytmusic_cli.db.db import BaseModel


class User(BaseModel):
    username = TextField(null=False, unique=True)
    default_volume = IntegerField(null=False, default=DEFAULT_VOLUME)
    search_limit = IntegerField(null=False, default=DEFAULT_SEARCH_LIMIT)
