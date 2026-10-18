"""Let catalog tracks come from any TuneMyMusic source, not only from Apple Music exports."""

import re

import sqlalchemy as sa

from alembic import op

revision = "0007_catalog_track_sources"
down_revision = "0006_track_isrc"
branch_labels = None
depends_on = None

TABLE = "music_catalog_tracks"
APPLE_ID_NOT_NULL = re.compile(r"(apple_track_id\s+VARCHAR\(32\))\s+NOT NULL", re.IGNORECASE)
APPLE_ID_NULLABLE = re.compile(r"(apple_track_id\s+VARCHAR\(32\))(?!\s+NOT NULL)", re.IGNORECASE)


def _rewrite_sqlite_table_sql(pattern: re.Pattern[str], replacement: str) -> None:
    """
    Changes only the NOT NULL flag of apple_track_id in the stored schema.

    Rebuilding the table instead would drop the old one, and with foreign keys on SQLite would then
    clear every file and playlist link to the catalog. This is the procedure SQLite documents for
    removing NOT NULL constraints (https://www.sqlite.org/lang_altertable.html#otheralter).
    """
    bind = op.get_bind()
    sql = bind.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (TABLE,)).scalar()
    updated = pattern.sub(replacement, sql or "", count=1)
    if not sql or updated == sql:
        return
    version = bind.exec_driver_sql("PRAGMA schema_version").scalar()
    bind.exec_driver_sql("PRAGMA writable_schema = ON")
    bind.exec_driver_sql("UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = ?", (updated, TABLE))
    bind.exec_driver_sql(f"PRAGMA schema_version = {int(version) + 1}")
    bind.exec_driver_sql("PRAGMA writable_schema = OFF")


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"]: column for column in sa.inspect(bind).get_columns(TABLE)}
    if not columns["apple_track_id"]["nullable"]:
        if bind.dialect.name == "sqlite":
            _rewrite_sqlite_table_sql(APPLE_ID_NOT_NULL, r"\1")
        else:
            op.alter_column(TABLE, "apple_track_id", existing_type=sa.String(32), nullable=True)
    if "source_service" not in columns:
        op.add_column(TABLE, sa.Column("source_service", sa.String(40), nullable=True))
    if "source_track_id" not in columns:
        op.add_column(TABLE, sa.Column("source_track_id", sa.String(128), nullable=True))
    if "idx_music_catalog_tracks_source" not in {index["name"] for index in sa.inspect(bind).get_indexes(TABLE)}:
        op.create_index("idx_music_catalog_tracks_source", TABLE, ["source_service", "source_track_id"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("idx_music_catalog_tracks_source", table_name=TABLE)
    # Tracks imported without an Apple id cannot exist in the previous schema.
    op.execute(f"DELETE FROM {TABLE} WHERE apple_track_id IS NULL")
    op.drop_column(TABLE, "source_track_id")
    op.drop_column(TABLE, "source_service")
    if bind.dialect.name == "sqlite":
        _rewrite_sqlite_table_sql(APPLE_ID_NULLABLE, r"\1 NOT NULL")
    else:
        op.alter_column(TABLE, "apple_track_id", existing_type=sa.String(32), nullable=False)
