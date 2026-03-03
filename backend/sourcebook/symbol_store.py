"""SQLite-backed symbol index for precision AI context retrieval."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from sourcebook.config import settings
from sourcebook.scanner import SKIP_DIRS
from sourcebook.symbol_extractor import ExtractedSymbol, extract_symbols_from_file

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_SYMBOLS_TABLE = """\
CREATE TABLE IF NOT EXISTS symbols (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    qualified_name    TEXT NOT NULL,
    kind              TEXT NOT NULL,
    signature         TEXT NOT NULL,
    file_path         TEXT NOT NULL,
    line_number       INTEGER NOT NULL,
    byte_offset_start INTEGER NOT NULL,
    byte_offset_end   INTEGER NOT NULL,
    summary           TEXT DEFAULT ''
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_symbols_file_path ON symbols (file_path);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols (name);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_qualified_name ON symbols (qualified_name);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols (kind);",
]


async def init_symbol_tables() -> None:
    """Create the symbols table and indexes if they don't exist."""
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(_CREATE_SYMBOLS_TABLE)
        for idx_sql in _CREATE_INDEXES:
            await db.execute(idx_sql)
        await db.commit()


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def _walk_project_files(project_root: Path) -> list[Path]:
    """Walk project tree, respecting SKIP_DIRS and file-size limits."""
    files: list[Path] = []
    for item in sorted(project_root.rglob("*")):
        if item.is_dir():
            continue
        # Skip if any parent directory is in SKIP_DIRS
        if any(part in SKIP_DIRS for part in item.relative_to(project_root).parts):
            continue
        if item.suffix in (".py", ".ts", ".tsx", ".js", ".jsx"):
            files.append(item)
    return files


async def build_symbol_index(project_root: Path) -> int:
    """Extract symbols from all project files and store in SQLite.

    Returns the number of symbols indexed.
    """
    project_files = _walk_project_files(project_root)

    all_symbols: list[ExtractedSymbol] = []
    for fpath in project_files:
        all_symbols.extend(extract_symbols_from_file(fpath, project_root))

    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("DELETE FROM symbols")
        for sym in all_symbols:
            await db.execute(
                """INSERT INTO symbols
                   (name, qualified_name, kind, signature, file_path,
                    line_number, byte_offset_start, byte_offset_end, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sym.name, sym.qualified_name, sym.kind, sym.signature,
                    sym.file_path, sym.line_number,
                    sym.byte_offset_start, sym.byte_offset_end,
                    sym.summary,
                ),
            )
        # Store timestamp
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('symbol_index_built_at', ?)",
            (datetime.now(UTC).isoformat(),),
        )
        await db.commit()

    return len(all_symbols)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL_SPLIT_RE = re.compile(r"[A-Z][a-z]+|[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)")

# Common words that shouldn't be treated as symbol search terms
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "because", "but", "and",
    "or", "if", "while", "about", "this", "that", "these", "those", "what",
    "which", "who", "whom", "it", "its", "my", "your", "his", "her",
    "we", "they", "them", "our", "me", "i", "you", "he", "she",
    "work", "works", "working", "use", "uses", "using", "make", "makes",
    "get", "gets", "set", "sets", "add", "adds", "new", "old",
    "file", "files", "code", "function", "class", "method", "variable",
    "import", "export", "return", "async", "await", "def", "const", "let",
    "var", "type", "interface",
}


def _extract_search_terms(
    message: str, diagram_nodes: list[dict]
) -> tuple[list[str], list[str]]:
    """Extract identifier-like terms from the user message and file paths from diagram nodes.

    Returns (terms, file_paths).
    """
    # Extract identifiers from message
    raw_tokens = _IDENT_RE.findall(message)
    terms: list[str] = []
    seen: set[str] = set()

    for token in raw_tokens:
        lower = token.lower()
        if lower in _STOP_WORDS or len(token) < 3:
            continue
        if lower not in seen:
            seen.add(lower)
            terms.append(token)

    # Extract file_path values from diagram nodes
    file_paths: list[str] = []
    for node in diagram_nodes:
        fp = node.get("file_path")
        if fp:
            file_paths.append(fp)

    return terms, file_paths


async def _query_symbols(
    terms: list[str],
    file_paths: list[str],
    limit: int = 30,
) -> list[dict]:
    """Query the symbol table with scoring.

    Scoring: exact name match (3) > qualified_name contains (2) > summary contains (1)
    Boost +2 for symbols in diagram-referenced files.
    """
    if not terms:
        return []

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row

        # Build a UNION query for each term with scoring
        union_parts: list[str] = []
        params: list[str] = []

        for term in terms[:15]:  # Cap at 15 terms to avoid huge queries
            lower_term = term.lower()
            # Exact name match (score 3)
            union_parts.append(
                "SELECT *, 3 AS score FROM symbols WHERE LOWER(name) = ?"
            )
            params.append(lower_term)
            # Qualified name contains (score 2)
            union_parts.append(
                "SELECT *, 2 AS score FROM symbols"
                " WHERE LOWER(qualified_name) LIKE ? AND LOWER(name) != ?"
            )
            params.append(f"%{lower_term}%")
            params.append(lower_term)
            # Summary contains (score 1)
            union_parts.append(
                "SELECT *, 1 AS score FROM symbols"
                " WHERE LOWER(summary) LIKE ?"
                " AND LOWER(name) != ?"
                " AND LOWER(qualified_name) NOT LIKE ?"
            )
            params.append(f"%{lower_term}%")
            params.append(lower_term)
            params.append(f"%{lower_term}%")

        sql = (
            "SELECT id, name, qualified_name, kind, signature, file_path, "
            "line_number, summary, MAX(score) AS max_score "
            f"FROM ({' UNION ALL '.join(union_parts)}) "
            "GROUP BY id "
            "ORDER BY max_score DESC, name ASC "
            f"LIMIT {limit * 2}"  # fetch extra, we'll re-rank with file boost
        )

        async with db.execute(sql, params) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    # Apply file path boost
    file_path_set = set(file_paths)
    for row in rows:
        if row["file_path"] in file_path_set:
            row["max_score"] = row["max_score"] + 2

    # Re-sort and limit
    rows.sort(key=lambda r: (-r["max_score"], r["name"]))
    return rows[:limit]


def _format_symbol_context(symbols: list[dict], max_chars: int = 3000) -> str | None:
    """Format symbols into a compact string for prompt injection."""
    if not symbols:
        return None

    lines: list[str] = []
    total = 0

    for sym in symbols:
        line = f"[{sym['kind']}] {sym['qualified_name']} -- {sym['signature']}"
        loc = f"  {sym['file_path']}:{sym['line_number']}"
        if sym.get("summary"):
            loc += f" -- {sym['summary']}"

        entry = f"{line}\n{loc}"
        entry_len = len(entry) + 1  # +1 for separator newline

        if total + entry_len > max_chars:
            break
        lines.append(entry)
        total += entry_len

    return "\n".join(lines) if lines else None


async def get_symbol_context(
    user_message: str,
    diagram_nodes: list[dict],
    max_symbols: int = 30,
    max_chars: int = 3000,
) -> str | None:
    """Retrieve relevant symbol context for a user message.

    Returns a formatted string suitable for prompt injection, or None if
    no relevant symbols are found.
    """
    terms, file_paths = _extract_search_terms(user_message, diagram_nodes)
    if not terms:
        return None

    symbols = await _query_symbols(terms, file_paths, limit=max_symbols)
    return _format_symbol_context(symbols, max_chars=max_chars)
