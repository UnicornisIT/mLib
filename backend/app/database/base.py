from app.auth.models import User
from app.modules.books.models import Book
from app.modules.collections.models import Collection, CustomField, Item, ItemFieldValue, ItemPhoto, Tag
from app.modules.games.models import Game
from app.modules.movie.models import (
    EpisodeWatch,
    MediaTitle,
    MovieSetting,
    TitleTracking,
    VideoFile,
    VideoUpload,
    WatchProgress,
)
from app.modules.music.models import Album, Artist, Artwork, Favorite, MusicSetting, Playlist, PlaylistTrack, Track
from app.modules.wishes.models import Wish
from app.settings.models import CoreSetting

__all__ = [
    "Album",
    "Artist",
    "Artwork",
    "Book",
    "Collection",
    "CustomField",
    "CoreSetting",
    "EpisodeWatch",
    "Favorite",
    "Game",
    "Wish",
    "Item",
    "ItemFieldValue",
    "ItemPhoto",
    "MediaTitle",
    "MovieSetting",
    "MusicSetting",
    "Playlist",
    "PlaylistTrack",
    "Track",
    "Tag",
    "TitleTracking",
    "User",
    "VideoFile",
    "VideoUpload",
    "WatchProgress",
]
