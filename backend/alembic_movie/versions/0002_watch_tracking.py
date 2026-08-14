"""Add title and episode watch tracking."""

import sqlalchemy as sa

from alembic import op

revision = "0002_watch_tracking"
down_revision = "0001_movie"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("movie_titles")}
    title_columns = (
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("episode_runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("total_episodes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_seasons", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seasons", sa.Text(), nullable=False, server_default="[]"),
    )
    for column in title_columns:
        if column.name not in existing_columns:
            op.add_column("movie_titles", column)

    existing_tables = set(inspector.get_table_names())
    if "movie_title_tracking" not in existing_tables:
        op.create_table(
            "movie_title_tracking",
            sa.Column("user_id", sa.String(36), primary_key=True),
            sa.Column(
                "title_id",
                sa.String(36),
                sa.ForeignKey("movie_titles.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column("watched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    tracking_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("movie_title_tracking")}
    if "idx_movie_tracking_user_status" not in tracking_indexes:
        op.create_index("idx_movie_tracking_user_status", "movie_title_tracking", ["user_id", "status"])

    if "movie_episode_watches" not in existing_tables:
        op.create_table(
            "movie_episode_watches",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column(
                "title_id",
                sa.String(36),
                sa.ForeignKey("movie_titles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("season_number", sa.Integer(), nullable=False),
            sa.Column("episode_number", sa.Integer(), nullable=False),
            sa.Column("tmdb_episode_id", sa.Integer(), nullable=True),
            sa.Column("episode_name", sa.String(500), nullable=True),
            sa.Column("runtime_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("watched_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "user_id", "title_id", "season_number", "episode_number", name="uq_movie_episode_watch"
            ),
        )
    episode_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("movie_episode_watches")}
    if "idx_movie_episode_watch_user_date" not in episode_indexes:
        op.create_index("idx_movie_episode_watch_user_date", "movie_episode_watches", ["user_id", "watched_at"])


def downgrade() -> None:
    op.drop_index("idx_movie_episode_watch_user_date", table_name="movie_episode_watches")
    op.drop_table("movie_episode_watches")
    op.drop_index("idx_movie_tracking_user_status", table_name="movie_title_tracking")
    op.drop_table("movie_title_tracking")
    op.drop_column("movie_titles", "seasons")
    op.drop_column("movie_titles", "total_seasons")
    op.drop_column("movie_titles", "total_episodes")
    op.drop_column("movie_titles", "episode_runtime_minutes")
    op.drop_column("movie_titles", "runtime_minutes")
