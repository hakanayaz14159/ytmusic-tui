from peewee import IntegerField, TextField

from ytmusic_tui.db.db import BaseModel


class Song(BaseModel):
    video_id = TextField(null=False, unique=True)
    title = TextField(null=False)
    artist = TextField(null=True)
    album = TextField(null=True)
    duration = IntegerField(null=True)
