from typing import Any

from pydantic import BaseModel, Field


class DataPathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=32767)
    client_state: dict[str, Any] | None = None


class DataOperationResult(BaseModel):
    status: str
    path: str
    kind: str
    message: str
    safety_backup: str | None = None
    client_state: dict[str, Any] | None = None


class DataTransferStatus(BaseModel):
    desktop: bool
    data_root: str | None
    media_root: str
    backups_root: str
    export_version: int
    schema_version: int
