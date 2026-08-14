PYTHON ?= python
PNPM ?= pnpm

.PHONY: dev-backend dev-frontend test lint typecheck build e2e migrate

dev-backend:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload

dev-frontend:
	cd frontend && $(PNPM) dev

migrate:
	cd backend && $(PYTHON) -m alembic -n core upgrade head
	cd backend && $(PYTHON) -m alembic -n music upgrade head
	cd backend && $(PYTHON) -m alembic -n movie upgrade head
	cd backend && $(PYTHON) -m alembic -n books upgrade head
	cd backend && $(PYTHON) -m alembic -n collections upgrade head
	cd backend && $(PYTHON) -m alembic -n games upgrade head
	cd backend && $(PYTHON) -m alembic -n wishes upgrade head

test:
	cd backend && $(PYTHON) -m pytest

lint:
	cd backend && $(PYTHON) -m ruff check app tests
	cd frontend && $(PNPM) lint

typecheck:
	cd frontend && $(PNPM) typecheck

build:
	cd frontend && $(PNPM) build

e2e:
	cd frontend && $(PNPM) test:e2e
