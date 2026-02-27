# Sourcebook

Architecture-first development tool. Design systems visually, implement with AI.

See [CONCEPT.md](./CONCEPT.md) for the full vision.

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- Claude Code CLI installed and authenticated (`claude --version` should work)

### Install dependencies (once)

```bash
make install
```

### Run

```bash
make dev
# Open http://localhost:8000
```

That's it. `make dev` builds the SvelteKit frontend and starts the FastAPI server which serves everything on **one port**.

## Development Commands

| Command | Description |
|---|---|
| `make install` | Install all frontend and backend dependencies |
| `make dev` | Build frontend + start backend with hot reload on :8000 |
| `make start` | Build frontend + start backend (production, no reload) |
| `make build` | Build frontend only (outputs to `backend/static/`) |
| `npm run check` (in `frontend/`) | Svelte type checking |
| `npm run lint` (in `frontend/`) | ESLint + Prettier |
| `pytest` (in `backend/`) | Run backend tests |
| `ruff check .` (in `backend/`) | Lint Python |
| `ruff format .` (in `backend/`) | Format Python |

> **Frontend dev server**: If you want Vite HMR during frontend development, you can still run `npm run dev` inside `frontend/` alongside the backend — the Vite dev proxy is not configured by default but the backend remains reachable at :8000.

## Architecture

```
Browser → http://localhost:8000
              │
        [FastAPI :8000]
          ├── GET  /         → serves built SvelteKit SPA
          ├── GET  /health   → health check
          ├── WS   /ws/{id}  → WebSocket handler
          ├── AI Agent (Claude CLI subprocess)
          └── Persistence (SQLite)
```

## Environment Variables

**Backend** (`backend/.env`) — all optional:
```
DB_PATH=sourcebook.db
CLAUDE_BIN=/usr/local/bin/claude   # only needed if claude is not in PATH
CLAUDE_MODEL=claude-sonnet-4-5     # override the default model
```

The backend invokes `claude --print --output-format stream-json` as a subprocess. No API key is required — it uses the auth from your existing Claude Code installation.
