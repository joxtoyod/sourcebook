.PHONY: install build dev start

install:
	cd frontend && npm install
	cd backend && pip install -e ".[dev]"

build:
	cd frontend && npm run build

dev: build
	cd backend && uvicorn sourcebook.main:app --reload --host 0.0.0.0 --port 8000

start: build
	cd backend && uvicorn sourcebook.main:app --host 0.0.0.0 --port 8000
