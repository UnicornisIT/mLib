"""Allow playlist entries that point at catalog tracks without a file."""

import sqlalchemy as sa

from alembic import op

revision = "0005_playlist_catalog_items"
down_revision = "0004_library_transfer"
branch_labels = None
depends_on = None

SOURCE_CHECK = (
    "(track_id IS NOT NULL AND catalog_track_id IS NULL) OR (track_id IS NULL AND catalog_track_id IS NOT NULL)"
)


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("music_playlist_tracks")}
    if "catalog_track_id" in columns:
        return
    # Nothing references music_playlist_tracks, so rebuilding it on SQLite cannot cascade anywhere.
    with op.batch_alter_table("music_playlist_tracks", recreate="auto") as batch:
        batch.add_column(sa.Column("catalog_track_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_music_playlist_tracks_catalog_track_id",
            "music_catalog_tracks",
            ["catalog_track_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.alter_column("track_id", existing_type=sa.String(36), nullable=True)
        batch.create_check_constraint("ck_music_playlist_tracks_source", SOURCE_CHECK)
        batch.create_index("ix_music_playlist_tracks_catalog_track_id", ["catalog_track_id"])


def downgrade() -> None:
    # Entries whose catalog track already has a file keep pointing at that file; entries
    # without a file cannot exist in the previous schema and are removed.
    linked_file = (
        "SELECT music_tracks.id FROM music_tracks "
        "WHERE music_tracks.catalog_track_id = music_playlist_tracks.catalog_track_id"
    )
    op.execute(
        f"UPDATE music_playlist_tracks SET track_id = ({linked_file}), catalog_track_id = NULL "
        f"WHERE track_id IS NULL AND EXISTS ({linked_file})"
    )
    op.execute("DELETE FROM music_playlist_tracks WHERE track_id IS NULL")
    bind = op.get_bind()
    foreign_keys = [
        foreign_key["name"]
        for foreign_key in sa.inspect(bind).get_foreign_keys("music_playlist_tracks")
        if foreign_key["constrained_columns"] == ["catalog_track_id"] and foreign_key.get("name")
    ]
    with op.batch_alter_table("music_playlist_tracks", recreate="auto") as batch:
        batch.drop_index("ix_music_playlist_tracks_catalog_track_id")
        batch.drop_constraint("ck_music_playlist_tracks_source", type_="check")
        if bind.dialect.name != "sqlite":
            for name in foreign_keys:
                batch.drop_constraint(name, type_="foreignkey")
        batch.drop_column("catalog_track_id")
        batch.alter_column("track_id", existing_type=sa.String(36), nullable=False)
