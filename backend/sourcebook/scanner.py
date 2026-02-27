from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".sourcebook", ".svelte-kit", "target", "vendor", ".cache", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "coverage", ".tox", "eggs", ".eggs",
    "htmlcov", ".idea", ".vscode",
}

KEY_FILES = {
    "README.md", "README.rst", "README.txt",
    "package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    "main.py", "app.py", "index.ts", "index.js", "server.ts", "server.js",
    "manage.py", "wsgi.py", "asgi.py",
    "Makefile", "justfile",
}

PROJECT_TYPE_INDICATORS = [
    ("package.json", "Node.js"),
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("pom.xml", "Java (Maven)"),
    ("build.gradle", "Java (Gradle)"),
]


@dataclass
class ProjectSummary:
    project_type: str
    file_count: int
    text: str  # full text for AI prompt (tree + key file contents)


def _detect_project_type(root: Path) -> str:
    for filename, label in PROJECT_TYPE_INDICATORS:
        if (root / filename).exists():
            return label
    return "Unknown"


def _build_tree(root: Path, max_depth: int = 4, max_entries: int = 200) -> tuple[str, int]:
    """Walk directory tree, return (tree_text, total_file_count)."""
    lines: list[str] = [str(root)]
    file_count = 0
    entry_count = 0

    def walk(path: Path, depth: int, prefix: str) -> None:
        nonlocal file_count, entry_count
        if depth > max_depth or entry_count >= max_entries:
            return
        try:
            children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        dirs = [c for c in children if c.is_dir() and c.name not in SKIP_DIRS]
        files = [c for c in children if c.is_file()]
        file_count += len(files)

        all_entries = dirs + files
        for i, child in enumerate(all_entries):
            if entry_count >= max_entries:
                lines.append(f"{prefix}└── ... (truncated)")
                return
            is_last = i == len(all_entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{child.name}")
            entry_count += 1
            if child.is_dir():
                extension = "    " if is_last else "│   "
                walk(child, depth + 1, prefix + extension)

    walk(root, 1, "")
    return "\n".join(lines), file_count


def _read_key_files(root: Path, max_files: int = 20, max_chars: int = 2000) -> str:
    """Read contents of key files and return formatted string."""
    sections: list[str] = []
    found = 0

    def try_read(path: Path) -> None:
        nonlocal found
        if found >= max_files:
            return
        if not path.exists() or not path.is_file():
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars:
                content = content[:max_chars] + "\n... (truncated)"
            rel = path.relative_to(root)
            sections.append(f"=== {rel} ===\n{content}")
            found += 1
        except Exception:
            pass

    # Read root-level key files first
    for name in KEY_FILES:
        try_read(root / name)

    # Also scan one level deep for key files
    if found < max_files:
        try:
            for child in sorted(root.iterdir()):
                if child.is_dir() and child.name not in SKIP_DIRS:
                    for name in KEY_FILES:
                        try_read(child / name)
                        if found >= max_files:
                            break
                if found >= max_files:
                    break
        except PermissionError:
            pass

    return "\n\n".join(sections)


def build_project_summary(root: Path) -> ProjectSummary:
    """Walk `root` and build a ProjectSummary suitable for an AI prompt."""
    project_type = _detect_project_type(root)
    tree, file_count = _build_tree(root)
    key_file_contents = _read_key_files(root)

    parts = [
        f"Project directory: {root}",
        f"Detected type: {project_type}",
        f"File count (approx): {file_count}",
        "",
        "Directory tree:",
        tree,
    ]
    if key_file_contents:
        parts += ["", "Key file contents:", key_file_contents]

    return ProjectSummary(
        project_type=project_type,
        file_count=file_count,
        text="\n".join(parts),
    )


def build_condensed_summary(root: Path) -> ProjectSummary:
    """Lightweight summary for chat context: tree structure only, no file contents."""
    project_type = _detect_project_type(root)
    tree, file_count = _build_tree(root, max_depth=3, max_entries=150)
    parts = [
        f"Project: {root.name}",
        f"Type: {project_type}",
        f"Files: ~{file_count}",
        "",
        "Structure:",
        tree,
    ]
    return ProjectSummary(
        project_type=project_type,
        file_count=file_count,
        text="\n".join(parts),
    )


_CACHE_MARKER = "<!-- sourcebook-index:"


def save_to_cache(summary: ProjectSummary, cache_path: Path) -> None:
    """Persist a condensed ProjectSummary to a markdown cache file."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    header = (
        f"{_CACHE_MARKER} generated_at={ts} "
        f"project_type={summary.project_type} "
        f"file_count={summary.file_count} -->\n"
    )
    cache_path.write_text(header + summary.text, encoding="utf-8")


def load_from_cache(cache_path: Path) -> ProjectSummary | None:
    """Return a ProjectSummary from cache, or None if absent/invalid."""
    if not cache_path.exists():
        return None
    try:
        content = cache_path.read_text(encoding="utf-8")
        first_line, _, rest = content.partition("\n")
        if not first_line.startswith(_CACHE_MARKER):
            return None
        meta_str = first_line[len(_CACHE_MARKER):].rstrip(" -->").strip()
        meta: dict[str, str] = {}
        for token in meta_str.split():
            if "=" in token:
                k, v = token.split("=", 1)
                meta[k] = v
        return ProjectSummary(
            project_type=meta.get("project_type", "Unknown"),
            file_count=int(meta.get("file_count", 0)),
            text=rest,
        )
    except Exception:
        return None
