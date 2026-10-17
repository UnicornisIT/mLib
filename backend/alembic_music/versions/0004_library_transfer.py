"""Add catalog tracks and persistent library transfer jobs."""

import sqlalchemy as sa

from alembic import op

revision = "0004_library_transfer"
down_revision = "0003_metadata_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "music_transfer_jobs" not in tables:
        op.create_table(
            "music_transfer_jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.String(36), nullable=False),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("filename", sa.String(1000), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("storefronts", sa.String(80), nullable=False),
            sa.Column("create_playlists", sa.Boolean(), nullable=False),
            sa.Column("rows_total", sa.Integer(), nullable=False),
            sa.Column("unique_total", sa.Integer(), nullable=False),
            sa.Column("added", sa.Integer(), nullable=False),
            sa.Column("existing", sa.Integer(), nullable=False),
            sa.Column("enriched", sa.Integer(), nullable=False),
            sa.Column("not_found", sa.Integer(), nullable=False),
            sa.Column("errors", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.Text()),
            sa.Column("worker_token", sa.String(36)),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_music_transfer_jobs_status", "music_transfer_jobs", ["status"])
        op.create_index("idx_music_transfer_jobs_owner_created", "music_transfer_jobs", ["owner_id", "created_at"])
    if "music_catalog_tracks" not in tables:
        op.create_table(
            "music_catalog_tracks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("apple_track_id", sa.String(32), nullable=False, unique=True),
            sa.Column("isrc", sa.String(32)),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("artist_name", sa.String(500), nullable=False),
            sa.Column("album_title", sa.String(500)),
            sa.Column("normalized_title", sa.String(500), nullable=False),
            sa.Column("normalized_artist", sa.String(500), nullable=False),
            sa.Column("collection_id", sa.String(32)),
            sa.Column("apple_url", sa.Text()),
            sa.Column("artwork_url", sa.Text()),
            sa.Column("year", sa.Integer()),
            sa.Column("duration_ms", sa.Integer()),
            sa.Column("storefront", sa.String(8)),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column(
                "transfer_job_id",
                sa.String(36),
                sa.ForeignKey("music_transfer_jobs.id", ondelete="SET NULL"),
            ),
            sa.Column("enrich_status", sa.String(16), nullable=False),
            sa.Column("enrich_attempts", sa.Integer(), nullable=False),
            sa.Column("enriched_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_music_catalog_tracks_isrc", "music_catalog_tracks", ["isrc"])
        op.create_index(
            "idx_music_catalog_tracks_identity", "music_catalog_tracks", ["normalized_artist", "normalized_title"]
        )
        op.create_index(
            "idx_music_catalog_tracks_enrich", "music_catalog_tracks", ["transfer_job_id", "enrich_status"]
        )

    # Plain ADD COLUMN keeps existing rows in place: rebuilding music_tracks on SQLite with
    # foreign keys enabled would cascade-delete favorites and playlist items.
    columns = {column["name"] for column in inspector.get_columns("music_tracks")}
    if "catalog_track_id" not in columns:
        if op.get_bind().dialect.name == "sqlite":
            op.execute(
                "ALTER TABLE music_tracks ADD COLUMN catalog_track_id VARCHAR(36) "
                "REFERENCES music_catalog_tracks (id) ON DELETE SET NULL"
            )
        else:
            op.add_column("music_tracks", sa.Column("catalog_track_id", sa.String(36), nullable=True))
            op.create_foreign_key(
                "fk_music_tracks_catalog_track_id",
                "music_tracks",
                "music_catalog_tracks",
                ["catalog_track_id"],
                ["id"],
                ondelete="SET NULL",
            )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("music_tracks")}
    if "ix_music_tracks_catalog_track_id" not in indexes:
        op.create_index("ix_music_tracks_catalog_track_id", "music_tracks", ["catalog_track_id"], unique=True)


def _drop_catalog_column_sqlite() -> None:
    # A table-level foreign key (as created by create_all) blocks DROP COLUMN on SQLite, so the
    # table is rebuilt. Foreign keys are switched off first: otherwise dropping the old table
    # would cascade-delete favorites and playlist items that reference it.
    context = op.get_context()
    with context.autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("music_tracks", recreate="always") as batch:
            batch.drop_column("catalog_track_id")
    finally:
        with context.autocommit_block():
            op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_music_tracks_catalog_track_id", table_name="music_tracks")
    if bind.dialect.name == "sqlite":
        _drop_catalog_column_sqlite()
    else:
        for foreign_key in sa.inspect(bind).get_foreign_keys("music_tracks"):
            if foreign_key["constrained_columns"] == ["catalog_track_id"] and foreign_key.get("name"):
                op.drop_constraint(foreign_key["name"], "music_tracks", type_="foreignkey")
        op.drop_column("music_tracks", "catalog_track_id")
    op.drop_table("music_catalog_tracks")
    op.drop_table("music_transfer_jobs")
