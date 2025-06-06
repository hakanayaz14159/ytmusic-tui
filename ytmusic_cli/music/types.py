from typing import TypedDict


class Song(TypedDict):
    id: int
    title: str
    artist: str | None
    album: str | None
    duration: int
    url: str


class Playlist(TypedDict):
    id: int
    name: str
    songs: list[Song]


class User(TypedDict):
    id: int
    username: str
    playlists: list[Playlist]
