# Sourcebook

> Design your system. Implement with AI.

Sourcebook is an **architecture-first development tool** that flips the traditional coding workflow. Instead of writing code and reverse-engineering documentation from it, you **design your system visually first** — then an AI coding agent uses that diagram as its implementation spec.

---

## Why Sourcebook?

Vibe coding is powerful — but it has three problems that compound as your project grows.

---

### 1. Cognitive Overload

AI coding tools are generous with output. Ask for a feature and you get 500 lines across 8 files, instantly. The code often works. But **reading and understanding it is now your problem**.

Most developers can't hold a large, AI-generated codebase in their head. They lose the thread of their own system. Reviews become rubber stamps. Bugs hide in code nobody fully understood.

Sourcebook puts the architecture front and center — a visual diagram where every module, service, and data flow is explicit. Before a single line is written, you and the AI agree on *what the system is*. When code is generated, you already know where it belongs.

---

### 2. Your Codebase Is a Living Knowledge Base

Code changes. AI-generated code changes fast. The mental model you built last week is already stale.

Sourcebook treats your codebase as a **living knowledge base** rather than a pile of files. Static analysis (Tree-sitter) continuously parses your source and keeps the canvas diagram in sync with what actually exists. Drift between the design and the reality is surfaced immediately — not discovered six sprints later.

Human corrections are persisted as ground truth and survive future re-parses. The diagram stays honest as the system evolves.

---

### 3. Design First, Spend Less

Sending a sprawling codebase as context to a frontier model on every request is expensive. And expensive models don't automatically produce better systems — they produce more code.

Sourcebook inverts the cost curve: **use a capable model once to produce a precise, structured spec from your architecture diagram**. That spec — node by node, edge by edge — becomes the implementation blueprint. A cheaper, faster model can then execute each step faithfully, because the hard thinking is already done.

Design at the top. Implement at the bottom. Pay accordingly.

---

## What It Is

- **Visual canvas** — a pannable, zoomable SVG diagram where nodes are modules/components/services and edges are dependencies, data flow, or API calls.
- **AI chat pane** — a sidebar connected to Claude (via the Claude Code CLI). The agent has full context of your diagram and can generate, refactor, or explain code.
- **Diagram-as-prompt** — the serialized canvas state is the primary context sent to the AI. Architecture-driven generation, not vibes-driven generation.
- **Living documentation** — static analysis (Tree-sitter) keeps the diagram in sync with real code. Drift is visible, not hidden.
- **Human override system** — manually correct any AI-inferred element. Overrides persist as ground truth and survive future re-parses.

---

## Demo

![Sourcebook canvas showing a multi-module architecture with AI chat](docs/demo.png)

> *Place a screenshot or GIF here once the UI is stable.*

---

## Getting Started

### Prerequisites

| Requirement | Version |
|---|---|
| Node.js | 20+ |
| Python | 3.11+ |
| Claude Code CLI | latest (`claude --version` must work) |

Sourcebook uses the `claude` CLI subprocess for AI — **no API key required**. It reuses the auth from your existing Claude Code installation.

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/joxtoyod/sourcebook/main/install.sh | bash
```

This clones the repo, builds the frontend, and installs the `sourcebook` CLI globally. Run it again to update.

**Prerequisites**: Python 3.11+, Node.js 20+, and [Claude Code CLI](https://claude.ai/download).

#### Manual install (for development)

```bash
git clone https://github.com/joxtoyod/sourcebook.git
cd sourcebook
make install
```

### Run

```bash
# From any project directory:
sourcebook          # start the UI
sourcebook scan     # scan codebase and generate diagram
```

The `sourcebook` command starts the FastAPI backend and opens the UI in your browser. Everything runs on **one port** — no proxy, no separate processes.

---

## Development Commands

| Command | Description |
|---|---|
| `make install` | Install all frontend and backend dependencies |
| `make dev` | Build frontend + start backend with hot reload on `:8000` |
| `make start` | Build frontend + start backend (production mode) |
| `make build` | Build frontend only → outputs to `backend/static/` |
| `npm run check` *(in `frontend/`)* | Svelte type checking |
| `npm run lint` *(in `frontend/`)* | ESLint + Prettier |
| `pytest` *(in `backend/`)* | Run backend tests |
| `ruff check .` *(in `backend/`)* | Lint Python |
| `ruff format .` *(in `backend/`)* | Format Python |

---

## Configuration

Create a `backend/.env` file to override defaults (all optional):

```env
DB_PATH=sourcebook.db
CLAUDE_BIN=/usr/local/bin/claude   # only if claude is not in PATH
CLAUDE_MODEL=claude-sonnet-4-5     # override the default model
```

---

## Architecture

```
Browser → http://localhost:8000
               │
         [FastAPI :8000]
           ├── GET  /         → serves built SvelteKit SPA (backend/static/)
           ├── GET  /health   → health check
           ├── WS   /ws/{id}  → WebSocket handler (streaming AI + diagram updates)
           ├── AI Agent       → claude CLI subprocess (stream-json output)
           ├── Scanner        → Tree-sitter static analysis (code → diagram sync)
           └── SQLite         → diagram layout, overrides, history
```

### Key Files

| File | Purpose |
|---|---|
| `backend/sourcebook/main.py` | FastAPI app entry point, static file serving |
| `backend/sourcebook/ws_handler.py` | WebSocket message loop, AI streaming, persistence |
| `backend/sourcebook/ai_agent.py` | Claude CLI subprocess, prompt building, stream parsing |
| `backend/sourcebook/database.py` | SQLite schema, diagram CRUD, override persistence |
| `backend/sourcebook/scanner.py` | Static analysis, codebase → diagram extraction |
| `frontend/src/lib/components/Canvas.svelte` | SVG canvas with pan/zoom/drag/drop |
| `frontend/src/lib/components/ChatPane.svelte` | Chat UI connected via WebSocket |
| `frontend/src/lib/stores/diagram.ts` | Diagram state (nodes/edges) as a Svelte store |

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | SvelteKit (TypeScript) |
| Backend | Python FastAPI |
| AI | Claude via `claude` CLI subprocess |
| Real-time | WebSocket (bidirectional streaming) |
| Canvas | Custom SVG renderer |
| Code analysis | Tree-sitter (multi-language) |
| Database | SQLite (local persistence) |

---

## How It Works

1. **Design** — Open the canvas. Lay out modules, services, data models, and their relationships. Use the AI chat to propose or refine the architecture from a description.
2. **Refine** — The AI generates a detailed diagram. Review, adjust, and approve. Each node and edge becomes a structured spec.
3. **Implement** — Trigger the AI coding agent to generate code module-by-module, using the diagram as its authoritative context.
4. **Sync** — As code evolves, Sourcebook re-parses the source and updates the diagram. Drift surfaces. Human overrides persist.

---

## What Sourcebook Is Not

- **Not an IDE.** It sits alongside VS Code or whatever editor you use.
- **Not just a diagramming tool.** Unlike Miro or draw.io, diagrams are backed by real code structure and drive actual implementation.
- **Not a CI/CD tool.** It doesn't build, test, or deploy.

---

## Contributing

Contributions are welcome. Please open an issue first to discuss significant changes.

```bash
# After making changes
npm run lint        # in frontend/
ruff check .        # in backend/
pytest              # in backend/
```

---

## License

MIT — see [LICENSE](./LICENSE).
