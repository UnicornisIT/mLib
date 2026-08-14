from dataclasses import replace
from typing import Protocol

from app.modules.music.metadata import NormalizedTrackMetadata


class MetadataProvider(Protocol):
    """Contract for rate-limited optional metadata providers."""

    name: str

    def enrich(self, metadata: NormalizedTrackMetadata) -> dict[str, object | None]: ...


class MetadataEnricher:
    """Fills only absent fields, preserving high-quality embedded tags."""

    fillable_fields = {"album", "genre", "year", "composer", "copyright", "comment", "artwork"}

    def __init__(self, providers: list[MetadataProvider] | None = None) -> None:
        self.providers = providers or []

    def enrich(self, metadata: NormalizedTrackMetadata) -> NormalizedTrackMetadata:
        result = metadata
        for provider in self.providers:
            patch = provider.enrich(result)
            accepted = {
                key: value
                for key, value in patch.items()
                if key in self.fillable_fields and getattr(result, key) in (None, "") and value not in (None, "")
            }
            if accepted:
                result = replace(result, **accepted)
        return result
