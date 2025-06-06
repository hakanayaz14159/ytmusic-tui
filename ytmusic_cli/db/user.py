from peewee import TextField

from ytmusic_cli.db.db import BaseModel


class User(BaseModel):
    username = TextField(null=False, unique=True)
