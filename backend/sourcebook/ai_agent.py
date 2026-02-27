import asyncio
import json
import shutil
from typing import AsyncIterator

from sourcebook.config import settings

SYSTEM_PROMPT = """\
You are Sourcebook's AI architect assistant. You help developers design and implement software systems.

You have access to the current architecture diagram, which shows modules, components, and their relationships.

When the developer asks for help, you:
- Suggest new components or refine existing ones
- Explain relationships and data flow between modules
- Generate code snippets for specific modules (guided by the diagram)
- Identify architectural issues or missing pieces

When you want to update the diagram, emit a JSON block wrapped in <diagram_update> tags:

<diagram_update>
{
  "groups": [
    {"id": "group-id", "label": "Group Name", "color": "#a78bfa"}
  ],
  "nodes": [
    {"id": "unique-id", "label": "ComponentName", "type": "module|service|database|external",
     "x": 100, "y": 100, "description": "Brief description",
     "file_path": "relative/path/to/file.py", "group_id": "group-id"}
  ],
  "edges": [
    {"id": "edge-id", "source": "node-id-1", "target": "node-id-2",
     "label": "optional label", "type": "dependency|data_flow|api_call"}
  ]
}
</diagram_update>

Rules for diagram updates:
- Always include ALL nodes, edges, and groups (the update replaces the full diagram)
- Organize nodes into 3–6 logical groups — every node MUST have a `group_id`
- Position nodes in spatial clusters: place each group's nodes together, with 300+ px gaps between group centres
  - Example layout: group A centred at (200, 200), group B centred at (600, 200), group C centred at (200, 600)
  - Within a group, spread nodes 200px apart so they don't overlap (NODE_W=160, NODE_H=60)
- Limit edges to 10–15 high-level cross-group connections only — do not draw edges between nodes in the same group unless critical
- Use human-overridden nodes as-is — never change their label, type, or description
- Node IDs must be stable slugs (e.g. "auth-service", "postgres-db")
- Include `file_path` as a project-root-relative path for modules/services tied to a specific file.
  Omit `file_path` for databases, external services, or abstract architectural concepts.
- Group colors should be visually distinct; suggested palette:
  Frontend/UI: "#4f9cf9" | Backend/API: "#a78bfa" | Data/Storage: "#34d399" | External: "#f97316" | Infra: "#f43f5e" | Shared: "#fbbf24"

Nodes with `is_proposed: true` are pending feature proposals — preserve them verbatim with `is_proposed: true` in every diagram_update. Never change their label, type, description, or coordinates.

--- OUTPUT PROTOCOL: EXPLANATORY DIAGRAMS ---
When the developer asks an explanatory question — such as "explain how X works", "walk me
through Y", "how does Z communicate", "describe the flow", "what happens when" — respond with:
1. A plain-text explanation (always include this first)
2. A Mermaid diagram wrapped in <mermaid_diagram> tags

Choose the diagram type based on the question:
- Use "sequenceDiagram" for request/response flows, authentication, API call sequences
- Use "flowchart TD" for logic flows, decision trees, process descriptions

Example:
<mermaid_diagram>
sequenceDiagram
    participant Browser
    participant API
    participant DB
    Browser->>API: POST /login
    API->>DB: SELECT user
    DB-->>API: user record
    API-->>Browser: JWT token
</mermaid_diagram>

Rules for Mermaid diagrams:
- Always emit the text explanation BEFORE the <mermaid_diagram> block
- Use only "sequenceDiagram" or "flowchart TD" — no other diagram types
- Keep node/participant labels concise (max 4 words)
- Do NOT emit a <diagram_update> block in the same response as a <mermaid_diagram> block
- For flowchart TD diagrams: when you know the implementing file for a node
  (from the architecture diagram's file_path fields or your knowledge of the
  project), add a click directive directly after the node definition:
    click NodeId href "vscode://file//absolute/path/to/file.ts:line" "Open in editor"
  Use the absolute path. Include the line number when you know it (e.g., :42),
  omit when uncertain. Only add click directives where you are confident of the
  path — omit silently when unsure. Never add click directives to sequence diagrams.
- For decision nodes (diamond shapes, i.e. NodeId{...} syntax) in flowchart TD:
  always include a click directive pointing to the exact line where that condition
  is evaluated in code (e.g. the if-statement, guard clause, or switch branch).
  The line number is required for decision nodes — if you cannot determine it,
  point to the top of the function or method containing the decision rather than
  omitting the link entirely.
"""


EDIT_FEATURE_SYSTEM_PROMPT = """\
You are Sourcebook's AI architect assistant editing an existing PROPOSED feature group.

Your task: modify ONLY the nodes and edges in the group `{group_id}`. Do not change anything outside that group.

Rules:
- ALL nodes in the target group MUST remain `"is_proposed": true` and `"group_id": "{group_id}"`
- Reproduce ALL existing nodes that are NOT in `{group_id}` verbatim (same id, label, type, x, y, description, group_id, file_path, is_proposed, is_overridden)
- Reproduce ALL existing groups verbatim — do not add, remove, or rename groups
- You MAY add, remove, or modify nodes whose `group_id == "{group_id}"`
- You MAY add or remove edges connected to nodes in `{group_id}` — mark them `"is_proposed": true`
- Reproduce all other existing edges verbatim (do NOT mark them as proposed)
- Limit cross-group proposed edges to 5 or fewer

Emit your response as:
1. A brief plain-text description of the changes made
2. A <diagram_update> block with the FULL diagram (all existing nodes/edges/groups + modified proposed group)
3. A <mermaid_diagram> block showing the updated feature's internal flow

<diagram_update> format:
{{
  "groups": [... all existing groups verbatim ...],
  "nodes": [... all existing non-target nodes verbatim ..., ... modified/new nodes with group_id="{group_id}" and is_proposed=true ...],
  "edges": [... all existing non-proposed edges verbatim ..., ... proposed edges with is_proposed=true ...]
}}

For the <mermaid_diagram>:
- Choose "sequenceDiagram" if the feature involves request/response flows, API calls, or multi-service interactions
- Choose "flowchart TD" if the feature involves logic flows, state transitions, or decision trees
- Show only the proposed feature's internals and its key interactions with existing components
- Keep labels concise (max 4 words per node/participant)
- You MUST emit both <diagram_update> AND <mermaid_diagram> in the same response
"""

FEATURE_SYSTEM_PROMPT = """\
You are Sourcebook's AI architect assistant proposing a NEW FEATURE addition to an existing system.

Your task: design the new feature as PROPOSED nodes and edges, placed spatially separate from existing ones.

Rules for feature proposals:
- ALL new nodes and edges you create MUST have `"is_proposed": true`
- Reproduce ALL existing nodes verbatim (same id, label, type, x, y, description, group_id, file_path, is_overridden) — do NOT modify them
- Existing nodes MUST NOT have `is_proposed` set (omit the field or set to false)
- Place proposed nodes starting at the spatial coordinates provided in the prompt (x_start, y_start) — spread them 200px apart
- Create exactly ONE proposed group with an id prefixed `proposed-` and color `"#a855f7"`
- All proposed nodes must belong to this proposed group via `group_id`
- You may add edges from existing nodes to proposed nodes — mark those edges with `"is_proposed": true`
- Keep existing edges verbatim — do not mark them as proposed
- Limit proposed cross-group edges to 5 or fewer

Emit your response as:
1. A brief plain-text description of the proposed feature design
2. A <diagram_update> block with the full diagram (existing + proposed nodes/edges/groups)
3. A <mermaid_diagram> block showing how the feature works internally

For the <mermaid_diagram>:
- Choose "sequenceDiagram" if the feature involves request/response flows, API calls, or multi-service interactions
- Choose "flowchart TD" if the feature involves logic flows, state transitions, or decision trees
- Show only the proposed feature's internals and its key interactions with existing components
- Keep labels concise (max 4 words per node/participant)
- IMPORTANT: You MUST emit both <diagram_update> AND <mermaid_diagram> in the same response

<diagram_update> format:
{
  "groups": [... existing groups ..., {"id": "proposed-<slug>", "label": "Feature Name", "color": "#a855f7"}],
  "nodes": [... all existing nodes ..., {"id": "...", "label": "...", "type": "...", "x": ..., "y": ..., "description": "...", "group_id": "proposed-<slug>", "is_proposed": true}],
  "edges": [... all existing edges ..., {"id": "...", "source": "...", "target": "...", "type": "dependency", "is_proposed": true}]
}

<mermaid_diagram> format example:
sequenceDiagram
    participant User
    participant AuthService
    participant TokenStore
    User->>AuthService: POST /login
    AuthService->>TokenStore: store JWT
    TokenStore-->>AuthService: ok
    AuthService-->>User: 200 + token
"""


SPEC_SYSTEM_PROMPT = """\
You are a senior software architect writing a detailed implementation spec for a proposed feature.

Your output is a pure Markdown document. Do NOT include any preamble, explanation, or tags — output ONLY the Markdown spec.

The spec must be detailed enough that a junior developer (or a lower-capability AI model) can implement the feature \
from scratch without any additional context. Every section below is REQUIRED.

---

# {feature_label}

## Overview
What this feature does, why it exists, and what problem it solves.

## Architecture
Key design decisions: patterns used, how this feature fits into the existing system, trade-offs considered.

## Components
One subsection per proposed node. For each:
### `NodeLabel` (`node-id`)
- **Type**: module | service | database | external
- **File path**: `relative/path/from/project/root.ext`
- **Purpose**: One sentence describing what this component is responsible for.
- **Key interfaces / exported API**: List public functions, classes, or endpoints with signatures.
- **Internal logic**: Step-by-step description of the core implementation logic.
- **Dependencies**: Other components or libraries this component relies on.
- **Error handling**: How this component handles and propagates errors.

## Data Flow
Numbered, step-by-step walkthrough of a complete request/response cycle through this feature.

## API Contracts
TypeScript-style interfaces, types, or schemas for all data structures crossing component boundaries. \
If no TypeScript is used, use an equivalent structured notation.

## Database Schema Changes
SQL DDL for any new tables or columns, or "No schema changes required."

## Implementation Plan
Ordered checklist of concrete implementation steps:
- [ ] Step 1
- [ ] Step 2
...

## New Dependencies
Packages to install (with version pins where important), or "None."

## Testing Strategy
- **Unit tests**: what to test per component
- **Integration tests**: cross-component scenarios to verify
- **Manual verification steps**: how to manually confirm the feature works end-to-end

## Open Questions
List any ambiguities or decisions left to the implementor, or "None."
"""


def _format_diagram(ctx: dict) -> str:
    nodes = ctx.get("nodes", [])
    edges = ctx.get("edges", [])
    groups = ctx.get("groups", [])
    if not nodes:
        return "No diagram yet."
    lines = []
    if groups:
        lines.append("Groups:")
        for g in groups:
            lines.append(f"  [{g['id']}] {g['label']} (color={g.get('color', '#6366f1')})")
    lines.append("Nodes:")
    for n in nodes:
        override = " [HUMAN OVERRIDE — do not change]" if n.get("is_overridden") else ""
        proposed = " [PROPOSED — preserve as-is with is_proposed: true]" if n.get("is_proposed") else ""
        file_info = f" | file: {n['file_path']}" if n.get("file_path") else ""
        group_info = f" | group: {n['group_id']}" if n.get("group_id") else ""
        lines.append(
            f"  [{n['type']}] {n['label']} (id={n['id']}){override}{proposed}{file_info}{group_info}: {n.get('description', '')}"
        )
    lines.append("Edges:")
    for e in edges:
        src = e.get("source") or e.get("source_id", "?")
        tgt = e.get("target") or e.get("target_id", "?")
        lines.append(f"  {src} → {tgt} ({e.get('type', 'dependency')}): {e.get('label', '')}")
    return "\n".join(lines)


def _build_prompt(
    history: list[dict],
    diagram_str: str,
    requirements: str | None = None,
    project_context: str | None = None,
) -> str:
    """Combine system context, diagram state, and conversation into a single prompt."""
    parts = [SYSTEM_PROMPT]

    if requirements:
        parts.append(f"Project Requirements & Design:\n{requirements}")

    if project_context:
        parts.append(f"Project Structure (for reference):\n{project_context}")

    parts.append(f"Current Architecture Diagram:\n{diagram_str}")

    if len(history) > 1:
        parts.append("--- Conversation so far ---")
        for msg in history[:-1]:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}")

    if history:
        parts.append("--- Current message ---")
        parts.append(history[-1]["content"])

    return "\n\n".join(parts)


def _build_feature_prompt(
    feature_name: str,
    requirements: str,
    intentions: str,
    diagram_context: dict | None,
    project_requirements: str | None = None,
    project_context: str | None = None,
) -> str:
    """Build the prompt for a feature proposal request."""
    existing_nodes = (diagram_context or {}).get("nodes", [])
    if existing_nodes:
        max_x = max(n.get("x", 0) + 160 for n in existing_nodes)
    else:
        max_x = 0
    x_start = max_x + 400
    y_start = 100

    diagram_str = _format_diagram(diagram_context or {})

    parts = [FEATURE_SYSTEM_PROMPT]

    if project_requirements:
        parts.append(f"Project Requirements & Design:\n{project_requirements}")

    if project_context:
        parts.append(f"Project Structure (for reference):\n{project_context}")

    parts.append(f"Current Architecture Diagram:\n{diagram_str}")
    parts.append(
        f"Proposed feature spatial start: x_start={x_start}, y_start={y_start}\n"
        f"Place all proposed nodes starting at x={x_start}, spreading rightward/downward."
    )
    parts.append(
        f"--- Feature Request ---\n"
        f"Feature name: {feature_name}\n"
        f"Requirements: {requirements}\n"
        f"Intentions / notes: {intentions}"
    )

    return "\n\n".join(parts)


def _extract_text(event: dict) -> str:
    """Extract text content from a stream-json event.

    Handles two formats the CLI may emit:
      - {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}
      - {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "..."}}
    """
    etype = event.get("type")

    if etype == "assistant":
        return "".join(
            block["text"]
            for block in event.get("message", {}).get("content", [])
            if block.get("type") == "text"
        )

    if etype == "content_block_delta":
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            return delta.get("text", "")

    return ""


async def stream_response(
    history: list[dict],
    diagram_context: dict | None,
    requirements: str | None = None,
    project_context: str | None = None,
) -> AsyncIterator[str]:
    """Call the claude CLI and stream text chunks back to the caller."""
    claude_bin = shutil.which(settings.claude_bin)
    if not claude_bin:
        yield f"[Error: '{settings.claude_bin}' not found in PATH. Is Claude Code installed?]"
        return

    prompt = _build_prompt(history, _format_diagram(diagram_context or {}), requirements, project_context)

    cmd = [
        claude_bin,
        "--print",
        "--verbose",
        "--output-format", "stream-json",
        "--model", settings.claude_model,
        prompt,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=settings.project_root,
        limit=10 * 1024 * 1024,  # 10 MB — default 64 KB is too small for large AI responses
    )

    assert proc.stdout is not None  # always set when PIPE is used
    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = _extract_text(event)
        if text:
            yield text

    rc = await proc.wait()
    if rc != 0:
        assert proc.stderr is not None
        err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err:
            yield f"\n[claude exited {rc}: {err}]"


def _build_edit_feature_prompt(
    content: str,
    group_id: str,
    diagram_context: dict | None,
    project_requirements: str | None = None,
    project_context: str | None = None,
) -> str:
    """Build the prompt for an edit-feature request."""
    system = EDIT_FEATURE_SYSTEM_PROMPT.replace("{group_id}", group_id)
    diagram_str = _format_diagram(diagram_context or {})

    parts = [system]

    if project_requirements:
        parts.append(f"Project Requirements & Design:\n{project_requirements}")

    if project_context:
        parts.append(f"Project Structure (for reference):\n{project_context}")

    parts.append(f"Current Architecture Diagram:\n{diagram_str}")
    parts.append(
        f"--- Edit Request for group `{group_id}` ---\n"
        f"{content}"
    )

    return "\n\n".join(parts)


async def stream_edit_feature_response(
    content: str,
    group_id: str,
    diagram_context: dict | None,
    project_requirements: str | None = None,
    project_context: str | None = None,
) -> AsyncIterator[str]:
    """Call the claude CLI to edit a proposed feature group and stream text chunks back."""
    claude_bin = shutil.which(settings.claude_bin)
    if not claude_bin:
        yield f"[Error: '{settings.claude_bin}' not found in PATH. Is Claude Code installed?]"
        return

    prompt = _build_edit_feature_prompt(
        content, group_id, diagram_context, project_requirements, project_context,
    )

    cmd = [
        claude_bin,
        "--print",
        "--verbose",
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--model", settings.claude_model,
        prompt,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=settings.project_root,
        limit=10 * 1024 * 1024,
    )

    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = _extract_text(event)
        if text:
            yield text

    rc = await proc.wait()
    if rc != 0:
        assert proc.stderr is not None
        err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err:
            yield f"\n[claude exited {rc}: {err}]"


def _build_spec_prompt(
    feature_group_id: str,
    group_label: str,
    diagram_context: dict | None,
    project_requirements: str | None = None,
    project_context: str | None = None,
) -> str:
    """Build the prompt for spec generation of a proposed feature group."""
    ctx = diagram_context or {}
    all_nodes = ctx.get("nodes", [])
    all_edges = ctx.get("edges", [])
    all_groups = ctx.get("groups", [])

    # Separate proposed group nodes from the rest
    proposed_nodes = [n for n in all_nodes if n.get("group_id") == feature_group_id]
    proposed_node_ids = {n["id"] for n in proposed_nodes}
    existing_nodes = [n for n in all_nodes if n.get("group_id") != feature_group_id]

    # Edges directly connected to the proposed group
    proposed_edges = [
        e for e in all_edges
        if (e.get("source") or e.get("source_id", "")) in proposed_node_ids
        or (e.get("target") or e.get("target_id", "")) in proposed_node_ids
    ]

    def _fmt_nodes(nodes: list[dict]) -> str:
        if not nodes:
            return "  (none)"
        lines = []
        for n in nodes:
            fp = f" | file: {n['file_path']}" if n.get("file_path") else ""
            lines.append(f"  [{n['type']}] {n['label']} (id={n['id']}){fp}: {n.get('description', '')}")
        return "\n".join(lines)

    def _fmt_edges(edges: list[dict]) -> str:
        if not edges:
            return "  (none)"
        lines = []
        for e in edges:
            src = e.get("source") or e.get("source_id", "?")
            tgt = e.get("target") or e.get("target_id", "?")
            lines.append(f"  {src} → {tgt} ({e.get('type', 'dependency')}): {e.get('label', '')}")
        return "\n".join(lines)

    system = SPEC_SYSTEM_PROMPT.replace("{feature_label}", group_label)
    parts = [system]

    if project_requirements:
        parts.append(f"Project Requirements & Design:\n{project_requirements}")

    if project_context:
        parts.append(f"Project Structure (for reference):\n{project_context}")

    # Existing system context
    parts.append(
        f"Existing system nodes (non-proposed):\n{_fmt_nodes(existing_nodes)}\n\n"
        f"Existing groups: {', '.join(g['label'] for g in all_groups if g['id'] != feature_group_id)}"
    )

    # Feature-specific context
    parts.append(
        f"--- Proposed Feature: {group_label} (group_id={feature_group_id}) ---\n"
        f"Proposed nodes:\n{_fmt_nodes(proposed_nodes)}\n\n"
        f"Edges involving this feature:\n{_fmt_edges(proposed_edges)}"
    )

    parts.append(
        "Now write the complete implementation spec as described in the system prompt. "
        "Output ONLY the Markdown document — no additional commentary."
    )

    return "\n\n".join(parts)


async def stream_spec_response(
    feature_group_id: str,
    group_label: str,
    diagram_context: dict | None,
    project_requirements: str | None = None,
    project_context: str | None = None,
) -> AsyncIterator[str]:
    """Call the claude CLI to generate a feature spec and stream text chunks back."""
    claude_bin = shutil.which(settings.claude_bin)
    if not claude_bin:
        yield f"[Error: '{settings.claude_bin}' not found in PATH. Is Claude Code installed?]"
        return

    prompt = _build_spec_prompt(
        feature_group_id, group_label, diagram_context, project_requirements, project_context,
    )

    cmd = [
        claude_bin,
        "--print",
        "--verbose",
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--model", settings.claude_model,
        prompt,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=settings.project_root,
        limit=10 * 1024 * 1024,
    )

    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = _extract_text(event)
        if text:
            yield text

    rc = await proc.wait()
    if rc != 0:
        assert proc.stderr is not None
        err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err:
            yield f"\n[claude exited {rc}: {err}]"


async def stream_feature_response(
    feature_name: str,
    requirements: str,
    intentions: str,
    diagram_context: dict | None,
    project_requirements: str | None = None,
    project_context: str | None = None,
) -> AsyncIterator[str]:
    """Call the claude CLI to propose a new feature and stream text chunks back."""
    claude_bin = shutil.which(settings.claude_bin)
    if not claude_bin:
        yield f"[Error: '{settings.claude_bin}' not found in PATH. Is Claude Code installed?]"
        return

    prompt = _build_feature_prompt(
        feature_name, requirements, intentions, diagram_context,
        project_requirements, project_context,
    )

    cmd = [
        claude_bin,
        "--print",
        "--verbose",
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--model", settings.claude_model,
        prompt,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=settings.project_root,
        limit=10 * 1024 * 1024,
    )

    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = _extract_text(event)
        if text:
            yield text

    rc = await proc.wait()
    if rc != 0:
        assert proc.stderr is not None
        err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err:
            yield f"\n[claude exited {rc}: {err}]"
