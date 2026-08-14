import wave

from mutagen.id3 import TALB, TIT2, TPE1, TPE2, TRCK
from mutagen.wave import WAVE

from app.core.config import Settings
from app.modules.music.metadata import extract_metadata, normalize_identity


def tagged_wav(path, *, title: str = "A Real Title"):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00" * 8000)
    audio = WAVE(path)
    audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=[title]))
    audio.tags.add(TPE1(encoding=3, text=["The Artist"]))
    audio.tags.add(TPE2(encoding=3, text=["Various Artists"]))
    audio.tags.add(TALB(encoding=3, text=["Compilation"]))
    audio.tags.add(TRCK(encoding=3, text=["3/12"]))
    audio.save()


def test_identity_normalization_handles_case_and_whitespace():
    assert normalize_identity("  Linkin   Park ") == normalize_identity("linkin park")


def test_wav_id3_metadata_is_normalized(tmp_path):
    path = tmp_path / "fallback name.wav"
    tagged_wav(path)

    metadata = extract_metadata(path, path.name, Settings(ffprobe_path="__missing__"))
    assert metadata.title == "A Real Title"
    assert metadata.artist == "The Artist"
    assert metadata.album_artist == "Various Artists"
    assert metadata.album == "Compilation"
    assert metadata.track_number == 3
    assert metadata.title_from_filename is False
    assert metadata.artist_from_fallback is False
    assert 0.9 < metadata.duration < 1.1


def test_missing_title_and_artist_are_marked_as_fallbacks(tmp_path):
    path = tmp_path / "filename fallback.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00" * 8000)

    metadata = extract_metadata(path, path.name, Settings(ffprobe_path="__missing__"))

    assert metadata.title == "filename fallback"
    assert metadata.title_from_filename is True
    assert metadata.artist_from_fallback is True
