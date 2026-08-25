from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

root = Path(SPECPATH)
migration_folders = [
    "alembic_core",
    "alembic_music",
    "alembic_movie",
    "alembic_books",
    "alembic_collections",
    "alembic_games",
    "alembic_wishes",
]
datas = [(str(root / folder), folder) for folder in migration_folders]
binaries = collect_dynamic_libs("argon2") + collect_dynamic_libs("psycopg_binary")
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + collect_submodules("sqlalchemy.dialects.postgresql")
    + ["PIL._tkinter_finder", "psycopg", "psycopg_binary"]
)

a = Analysis(
    [str(root / "desktop_backend.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mlib-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="backend",
)
