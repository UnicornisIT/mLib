import logging
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings
from app.database.session import MusicSessionLocal
from app.modules.music.library import DuplicateTrackError, import_staged_file
from app.modules.music.models import Track
from app.storage.service import LocalMediaStorage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ImportJob:
    id: str
    path: str
    status: str = "queued"
    found: int = 0
    processed: int = 0
    added: int = 0
    skipped: int = 0
    errors: int = 0
    current_file: str | None = None
    error_message: str | None = None


class ImportJobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, ImportJob] = {}
        self._lock = threading.Lock()

    def create(self, path: Path) -> ImportJob:
        job = ImportJob(id=str(uuid.uuid4()), path=str(path))
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> ImportJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def snapshot(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return asdict(job) if job else None


jobs = ImportJobRegistry()


def scan_directory(job_id: str, root: Path, settings: Settings) -> None:
    job = jobs.get(job_id)
    if job is None:
        return
    job.status = "scanning"
    try:
        files = sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in settings.supported_audio_extensions
        )
        job.found = len(files)
        job.status = "processing"
        storage = LocalMediaStorage(settings)
        with MusicSessionLocal() as db:
            for source in files:
                job.current_file = source.name
                try:
                    known = db.scalar(
                        select(Track.id).where(
                            Track.source_path == str(source), Track.file_size == source.stat().st_size
                        )
                    )
                    if known:
                        job.skipped += 1
                    else:
                        staged = storage.stage_existing(source)
                        import_staged_file(db, staged, storage, settings, source_path=str(source))
                        job.added += 1
                except DuplicateTrackError:
                    job.skipped += 1
                except Exception:
                    logger.exception("Import failed for %s", source)
                    job.errors += 1
                finally:
                    job.processed += 1
        job.status = "completed"
        job.current_file = None
    except Exception as exc:
        logger.exception("Directory scan failed: %s", root)
        job.status = "failed"
        job.error_message = str(exc)
