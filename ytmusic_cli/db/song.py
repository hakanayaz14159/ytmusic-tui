from peewee import IntegerField, TextField

from ytmusic_cli.db.db import BaseModel


class Song(BaseModel):
    title = TextField(null=False)
    artist = TextField(null=True)
    duration = IntegerField(null=True)
    url = TextField(null=False)
