raise RuntimeError(
    "The legacy monolithic migration chain is retired. "
    "Use 'alembic -n core', 'alembic -n music' or 'alembic -n movie'."
)
