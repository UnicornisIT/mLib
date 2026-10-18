"""Case-insensitive text matching that also works for Cyrillic on SQLite.

SQLite's lower(), upper() and LIKE fold only ASCII letters, so "александр" never matched "Александр".
SQLite connections get a mlib_casefold() function backed by Python's str.casefold (see session.py);
other databases use lower(), which is Unicode-aware there.
"""

from typing import Any

from sqlalchemy import String
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import FunctionElement

SQLITE_CASEFOLD = "mlib_casefold"


class casefold(FunctionElement):  # noqa: N801 - reads like the SQL function it compiles to
    type = String()
    inherit_cache = True
    name = "casefold"


@compiles(casefold)
def _compile_casefold(element: casefold, compiler: Any, **kw: Any) -> str:
    return f"lower({compiler.process(element.clauses, **kw)})"


@compiles(casefold, "sqlite")
def _compile_casefold_sqlite(element: casefold, compiler: Any, **kw: Any) -> str:
    return f"{SQLITE_CASEFOLD}({compiler.process(element.clauses, **kw)})"


def sqlite_casefold(value: object) -> object:
    return value.casefold() if isinstance(value, str) else value


def contains_text(column: Any, query: str) -> ColumnElement[bool]:
    """column contains query, ignoring case in any alphabet; LIKE wildcards in the query are literal."""
    term = query.strip().casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return casefold(column).like(f"%{term}%", escape="\\")
