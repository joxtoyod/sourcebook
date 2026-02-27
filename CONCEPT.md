# Project Sourcebook — Concept Document

## 1. Vision

Project Sourcebook is an **architecture-first development tool**. It flips the traditional coding workflow: instead of writing code and then documenting it, you **design your system visually first**, then use AI to implement it.

At its core, Sourcebook is a **visual system architect** that lives alongside your source code. It renders your entire application as an interactive diagram — showing modules, dependencies, data flow, and logic — and that diagram doubles as the **authoritative prompt** that drives AI code generation.

---

## 2. Core Principles

### Architecture First
The diagram *is* the source of truth. Developers design components, relationships, and data flow on a visual canvas **before** any code is written. The AI coding agent then uses this diagram as its implementation spec.

### Living Documentation
Once code exists, Sourcebook uses **static analysis** to parse the codebase and keep the visual diagram in sync with the actual implementation. The diagram is never stale — it reflects the real state of the code at all times.

### Human-in-the-Loop
AI generates a "best guess" architecture from existing code or from natural-language descriptions. However, developers can **manually override** any element (rename modules, redraw relationships, correct misinterpretations). These human overrides are persisted as the **ground truth** and take precedence over AI inference.


---

## 3. How It Works — User Workflow

1. **Design Phase:** The developer opens Sourcebook's canvas and lays out the system architecture — components, services, data models, API boundaries, and their relationships — either manually or by describing it to the AI chat assistant.
2. **Refinement Phase:** The AI proposes a detailed architecture diagram. The developer reviews, adjusts, and confirms. Each node and edge on the diagram maps to a structured prompt/spec.
3. **Implementation Phase:** Once the architecture is approved, the developer triggers the AI coding agent (via the chat pane) to generate code module-by-module, guided by the diagram as context.
4. **Sync Phase:** As the codebase evolves, Sourcebook continuously re-parses the source code and updates the diagram. Drift between the diagram and code is surfaced to the developer.

---

## 4. Key Features

| Feature | Description |
|---|---|
| **Interactive Canvas** | A pannable, zoomable diagram where nodes represent modules/components and edges represent dependencies, data flow, or API calls. |
| **AI Chat Pane** | A sidebar chat interface connected to an AI coding agent. The agent has full context of the current diagram and can generate, modify, or explain code. |
| **Diagram-as-Prompt** | Every element on the canvas (node, edge, annotation) maps to a structured specification. When the AI implements code, it receives this spec as its prompt context. |
| **Manual Override & Persistence** | Developers can manually edit any AI-inferred element. Overrides are stored and treated as ground truth in future re-parses. |
| **Logic Flow Visualization** | Shows control flow and data flow within and between modules, not just structural relationships. |

---

## 5. Technical Architecture

### Frontend — SvelteKit Web Application
- **Interactive Canvas:** A pannable/zoomable diagram surface (candidates: Svelte Flow, D3.js, or custom Canvas/SVG renderer).
- **Chat Pane:** A sidebar chat UI for interacting with the AI coding agent.
- **State Management:** The canvas state (nodes, edges, overrides, annotations) is the core application state.
- **Communication:** Connects to the backend via **WebSocket** for real-time, bidirectional communication with the AI agent.

### Backend — Python FastAPI Server
- **WebSocket Endpoint:** Maintains a persistent connection with the frontend for streaming AI responses, agent actions, and real-time updates.
- **AI Coding Agent:** Orchestrates calls to an LLM (e.g., Claude). Receives the diagram spec as context and produces code, architecture suggestions, or answers.
- **Static Analysis Service:** Runs parsers (e.g., Tree-sitter) against the project's source files to extract structure and update the diagram model.
- **Persistence Layer:** Stores project state — diagram layout, human overrides, generated code mappings, and analysis cache in a local Sqlite.

### Data Flow
```
[SvelteKit Frontend]
        │
        │  WebSocket (bidirectional)
        ▼
[FastAPI Backend]
   ├── AI Agent (LLM calls)
   ├── Static Analysis Engine (Tree-sitter / language parsers)
   └── Persistence (project state, overrides, diagram data)
```

---

## 6. What Sourcebook Is NOT

- **Not an IDE.** It does not replace VS Code or any editor. It is a companion tool for visualization and AI-driven architecture.
- **Not just a diagramming tool.** Unlike Miro or draw.io, Sourcebook diagrams are backed by real code structure and drive actual implementation.
- **Not a CI/CD tool.** It does not build, test, or deploy code.

---

## 7. Success Criteria

A successful v1 of Sourcebook should allow a developer to:
1. Open a new project and design a multi-module architecture on the canvas via drag-and-drop or AI chat.
2. Trigger the AI agent to generate boilerplate code for each module based on the diagram.
3. Point Sourcebook at an existing codebase and have it auto-generate a visual architecture diagram.
4. Manually override AI-inferred relationships and have those overrides persist across re-parses.