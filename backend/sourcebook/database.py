import json
import uuid

import aiosqlite

from sourcebook.config import settings


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        # Migrate from old multi-project schema if needed
        try:
            async with db.execute("SELECT 1 FROM projects LIMIT 1") as cur:
                await cur.fetchone()
            # Old schema detected — drop everything and start fresh
            await db.executescript("""
                DROP TABLE IF EXISTS diagram_versions;
                DROP TABLE IF EXISTS diagram_edges;
                DROP TABLE IF EXISTS diagram_nodes;
                DROP TABLE IF EXISTS projects;
            """)
            await db.commit()
        except Exception:
            pass  # No projects table — fresh DB or already on new schema

        await db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS diagram_nodes (
                id            TEXT PRIMARY KEY,
                label         TEXT NOT NULL,
                type          TEXT NOT NULL,
                x             REAL DEFAULT 0,
                y             REAL DEFAULT 0,
                description   TEXT,
                is_overridden INTEGER DEFAULT 0,
                is_proposed   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS diagram_edges (
                id          TEXT PRIMARY KEY,
                source_id   TEXT NOT NULL,
                target_id   TEXT NOT NULL,
                label       TEXT,
                type        TEXT DEFAULT 'dependency',
                is_proposed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS diagram_versions (
                id         TEXT PRIMARY KEY,
                label      TEXT NOT NULL,
                nodes_json TEXT NOT NULL,
                edges_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mermaid_diagrams (
                id          TEXT PRIMARY KEY,
                title       TEXT DEFAULT 'Flow Diagram',
                syntax      TEXT NOT NULL,
                x           REAL DEFAULT 80,
                y           REAL DEFAULT 80,
                minimized   INTEGER DEFAULT 0,
                is_proposed INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS diagram_groups (
                id    TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#6366f1'
            );
        """)
        # Migrate existing DB: add title column if missing
        try:
            await db.execute("ALTER TABLE mermaid_diagrams ADD COLUMN title TEXT DEFAULT 'Flow Diagram'")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add is_proposed column to mermaid_diagrams if missing
        try:
            await db.execute("ALTER TABLE mermaid_diagrams ADD COLUMN is_proposed INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add file_path column if missing
        try:
            await db.execute("ALTER TABLE diagram_nodes ADD COLUMN file_path TEXT")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add group_id column to nodes if missing
        try:
            await db.execute("ALTER TABLE diagram_nodes ADD COLUMN group_id TEXT")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add groups_json column to versions if missing
        try:
            await db.execute("ALTER TABLE diagram_versions ADD COLUMN groups_json TEXT DEFAULT '[]'")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add is_proposed column to nodes if missing
        try:
            await db.execute("ALTER TABLE diagram_nodes ADD COLUMN is_proposed INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add is_proposed column to edges if missing
        try:
            await db.execute("ALTER TABLE diagram_edges ADD COLUMN is_proposed INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add feature_group_id column to mermaid_diagrams if missing
        try:
            await db.execute("ALTER TABLE mermaid_diagrams ADD COLUMN feature_group_id TEXT")
            await db.commit()
        except Exception:
            pass  # Column already exists
        # Migrate existing DB: add spec_path column to diagram_groups if missing
        try:
            await db.execute("ALTER TABLE diagram_groups ADD COLUMN spec_path TEXT")
            await db.commit()
        except Exception:
            pass  # Column already exists
        await db.commit()

    # Create symbol index tables (separate module manages the schema)
    from sourcebook.symbol_store import init_symbol_tables  # noqa: PLC0415
    await init_symbol_tables()


async def get_diagram() -> tuple[list[dict], list[dict], list[dict]]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM diagram_nodes") as cur:
            nodes = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT * FROM diagram_edges") as cur:
            edges = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT * FROM diagram_groups") as cur:
            groups = [dict(r) for r in await cur.fetchall()]
    return nodes, edges, groups


async def save_diagram(nodes: list[dict], edges: list[dict], groups: list[dict] | None = None) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("DELETE FROM diagram_nodes")
        await db.execute("DELETE FROM diagram_edges")
        await db.execute("DELETE FROM diagram_groups")
        for n in nodes:
            await db.execute(
                """INSERT INTO diagram_nodes
                   (id, label, type, x, y, description, is_overridden, is_proposed, file_path, group_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    n["id"], n["label"], n["type"],
                    n.get("x", 0), n.get("y", 0),
                    n.get("description"), int(n.get("is_overridden", False)),
                    int(n.get("is_proposed", False)),
                    n.get("file_path"),
                    n.get("group_id"),
                ),
            )
        for e in edges:
            await db.execute(
                """INSERT INTO diagram_edges
                   (id, source_id, target_id, label, type, is_proposed)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    e["id"],
                    e.get("source") or e.get("source_id"),
                    e.get("target") or e.get("target_id"),
                    e.get("label"), e.get("type", "dependency"),
                    int(e.get("is_proposed", False)),
                ),
            )
        for g in (groups or []):
            await db.execute(
                "INSERT INTO diagram_groups (id, label, color) VALUES (?, ?, ?)",
                (g["id"], g["label"], g.get("color", "#6366f1")),
            )
        await db.commit()


async def get_requirements() -> str | None:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT value FROM settings WHERE key = 'requirements_text'"
        ) as cur:
            row = await cur.fetchone()
            return row["value"] if row else None


async def update_requirements(requirements_text: str) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('requirements_text', ?)",
            (requirements_text,),
        )
        await db.commit()


async def get_project_name() -> str | None:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT value FROM settings WHERE key = 'project_name'"
        ) as cur:
            row = await cur.fetchone()
            return row["value"] if row else None


async def set_project_name(name: str) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('project_name', ?)",
            (name,),
        )
        await db.commit()


async def snapshot_diagram(nodes: list[dict], edges: list[dict], label: str, groups: list[dict] | None = None) -> None:
    """Snapshot the current diagram before an AI overwrite. Prunes to 20 versions."""
    MAX_VERSIONS = 20
    version_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO diagram_versions (id, label, nodes_json, edges_json, groups_json) VALUES (?, ?, ?, ?, ?)",
            (version_id, label[:120], json.dumps(nodes), json.dumps(edges), json.dumps(groups or [])),
        )
        await db.execute(
            "DELETE FROM diagram_versions WHERE id NOT IN ("
            "  SELECT id FROM diagram_versions ORDER BY created_at DESC LIMIT ?)",
            (MAX_VERSIONS,),
        )
        await db.commit()


async def list_versions() -> list[dict]:
    """Return all versions, newest first (metadata only)."""
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, label, created_at FROM diagram_versions ORDER BY created_at DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def restore_version(version_id: str) -> tuple[list[dict], list[dict], list[dict]] | None:
    """Restore a version to the live diagram. Returns (nodes, edges, groups) or None if not found."""
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT nodes_json, edges_json, groups_json FROM diagram_versions WHERE id = ?",
            (version_id,),
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    nodes = json.loads(row["nodes_json"])
    edges = json.loads(row["edges_json"])
    groups = json.loads(row["groups_json"] or "[]")
    await save_diagram(nodes, edges, groups)
    return nodes, edges, groups


async def save_mermaid_diagram(
    id: str, syntax: str, x: float = 80, y: float = 80,
    title: str = "Flow Diagram", is_proposed: bool = False,
    feature_group_id: str | None = None,
) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO mermaid_diagrams (id, title, syntax, x, y, minimized, is_proposed, feature_group_id) VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (id, title, syntax, x, y, int(is_proposed), feature_group_id),
        )
        await db.commit()


async def update_mermaid_syntax_for_group(feature_group_id: str, syntax: str) -> str | None:
    """Update the syntax of the proposed Mermaid card linked to a feature group.

    Returns the card ID if found and updated, otherwise None.
    """
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM mermaid_diagrams WHERE feature_group_id = ? AND is_proposed = 1",
            (feature_group_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        card_id = row["id"]
        await db.execute(
            "UPDATE mermaid_diagrams SET syntax = ? WHERE id = ?",
            (syntax, card_id),
        )
        await db.commit()
        return card_id


async def get_mermaid_diagrams() -> list[dict]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, title, syntax, x, y, minimized, is_proposed FROM mermaid_diagrams ORDER BY created_at"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def update_mermaid_diagram(id: str, **kwargs: float | int | str) -> None:
    allowed = {"x", "y", "minimized", "title"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [id]
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(f"UPDATE mermaid_diagrams SET {set_clause} WHERE id = ?", values)
        await db.commit()


async def delete_mermaid_diagram(id: str) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("DELETE FROM mermaid_diagrams WHERE id = ?", (id,))
        await db.commit()


async def apply_node_override(node_id: str, patch: dict) -> None:
    """Persist a human override on a single node."""
    fields = {k: v for k, v in patch.items() if k in ("label", "description", "x", "y", "type", "file_path")}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [1, node_id]
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            f"UPDATE diagram_nodes SET {set_clause}, is_overridden = ? WHERE id = ?",
            values,
        )
        await db.commit()


async def accept_feature(feature_group_id: str) -> None:
    """Accept all proposed nodes in a group and any edges touching those nodes."""
    async with aiosqlite.connect(settings.db_path) as db:
        # Accept all proposed nodes in the group
        await db.execute(
            "UPDATE diagram_nodes SET is_proposed = 0 WHERE group_id = ? AND is_proposed = 1",
            (feature_group_id,),
        )
        # Accept proposed edges where at least one endpoint is in the accepted group
        async with db.execute(
            "SELECT id FROM diagram_nodes WHERE group_id = ?",
            (feature_group_id,),
        ) as cur:
            node_ids = [row[0] for row in await cur.fetchall()]
        if node_ids:
            placeholders = ",".join("?" * len(node_ids))
            await db.execute(
                f"UPDATE diagram_edges SET is_proposed = 0"
                f" WHERE is_proposed = 1"
                f" AND (source_id IN ({placeholders}) OR target_id IN ({placeholders}))",
                node_ids + node_ids,
            )
        await db.commit()


async def reject_feature(feature_group_id: str) -> None:
    """Delete all proposed nodes in a group, their edges, and the group itself."""
    async with aiosqlite.connect(settings.db_path) as db:
        # Collect node IDs before deleting them
        async with db.execute(
            "SELECT id FROM diagram_nodes WHERE group_id = ?",
            (feature_group_id,),
        ) as cur:
            node_ids = [row[0] for row in await cur.fetchall()]
        if node_ids:
            placeholders = ",".join("?" * len(node_ids))
            await db.execute(
                f"DELETE FROM diagram_edges"
                f" WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})",
                node_ids + node_ids,
            )
            await db.execute(
                f"DELETE FROM diagram_nodes WHERE id IN ({placeholders})",
                node_ids,
            )
        await db.execute("DELETE FROM diagram_groups WHERE id = ?", (feature_group_id,))
        await db.commit()


async def accept_node(node_id: str) -> None:
    """Accept a single proposed node."""
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE diagram_nodes SET is_proposed = 0 WHERE id = ?",
            (node_id,),
        )
        await db.commit()


async def store_spec_path(feature_group_id: str, spec_path: str) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE diagram_groups SET spec_path = ? WHERE id = ?",
            (spec_path, feature_group_id),
        )
        await db.commit()


async def update_proposed_feature(feature_group_id: str, new_nodes: list[dict], new_edges: list[dict]) -> None:
    """Scoped merge: replace only the nodes/edges belonging to the target proposed group.

    Safety boundary: nodes not in new_nodes that belong to other groups are never touched.
    Even if the AI emits other nodes in new_nodes, only those with group_id == feature_group_id
    are accepted.
    """
    async with aiosqlite.connect(settings.db_path) as db:
        # 1. Find current node IDs in the target group
        async with db.execute(
            "SELECT id FROM diagram_nodes WHERE group_id = ?",
            (feature_group_id,),
        ) as cur:
            old_node_ids = [row[0] for row in await cur.fetchall()]

        # 2. Delete edges connected to those old nodes
        if old_node_ids:
            placeholders = ",".join("?" * len(old_node_ids))
            await db.execute(
                f"DELETE FROM diagram_edges"
                f" WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})",
                old_node_ids + old_node_ids,
            )
            await db.execute(
                f"DELETE FROM diagram_nodes WHERE id IN ({placeholders})",
                old_node_ids,
            )

        # 3. Insert scoped nodes — only those with group_id == feature_group_id (safety boundary)
        scoped_nodes = [n for n in new_nodes if n.get("group_id") == feature_group_id]
        scoped_node_ids = set()
        for n in scoped_nodes:
            scoped_node_ids.add(n["id"])
            await db.execute(
                """INSERT OR REPLACE INTO diagram_nodes
                   (id, label, type, x, y, description, is_overridden, is_proposed, file_path, group_id)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?, ?)""",
                (
                    n["id"], n["label"], n["type"],
                    n.get("x", 0), n.get("y", 0),
                    n.get("description"),
                    n.get("file_path"),
                    feature_group_id,
                ),
            )

        # 4. Insert new edges where at least one endpoint is in the new scoped node set
        for e in new_edges:
            src = e.get("source") or e.get("source_id", "")
            tgt = e.get("target") or e.get("target_id", "")
            if src in scoped_node_ids or tgt in scoped_node_ids:
                edge_id = e.get("id") or str(uuid.uuid4())
                await db.execute(
                    """INSERT OR REPLACE INTO diagram_edges
                       (id, source_id, target_id, label, type, is_proposed)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (
                        edge_id, src, tgt,
                        e.get("label"), e.get("type", "dependency"),
                    ),
                )

        await db.commit()
