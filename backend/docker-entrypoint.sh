#!/bin/sh
set -eu

alembic -n core upgrade head
alembic -n music upgrade head
alembic -n movie upgrade head
alembic -n books upgrade head
alembic -n collections upgrade head
alembic -n games upgrade head
alembic -n wishes upgrade head
exec "$@"
