"""Regex-based extraction of code symbols from Python and TypeScript/JavaScript files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedSymbol:
    name: str
    qualified_name: str
    kind: str  # function, class, method, variable, interface, type_alias
    signature: str
    file_path: str  # relative to project root
    line_number: int
    byte_offset_start: int
    byte_offset_end: int
    summary: str = ""


# ---------------------------------------------------------------------------
# Python extraction
# ---------------------------------------------------------------------------

_PY_CLASS_RE = re.compile(r"^class\s+(\w+)\s*(\([^)]*\))?\s*:", re.MULTILINE)
_PY_FUNC_RE = re.compile(
    r"^( *)(?:async\s+)?def\s+(\w+)\s*(\([^)]*\))(?:\s*->\s*([^\n:]+))?\s*:",
    re.MULTILINE,
)
_PY_ASSIGN_RE = re.compile(r"^([A-Z][A-Z_0-9]+)\s*[:=]", re.MULTILINE)
_PY_DOCSTRING_RE = re.compile(r'^\s*(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')', re.DOTALL)


def _first_docstring_line(source: str, func_end_offset: int) -> str:
    """Extract the first line of a docstring immediately following a def/class line."""
    rest = source[func_end_offset:]
    # Skip the colon + any whitespace/newline
    m = _PY_DOCSTRING_RE.match(rest)
    if not m:
        return ""
    doc = (m.group(1) or m.group(2) or "").strip()
    first_line = doc.split("\n")[0].strip()
    return first_line[:120]


def extract_python_symbols(source: str, rel_path: str) -> list[ExtractedSymbol]:
    symbols: list[ExtractedSymbol] = []
    module_name = rel_path.replace("/", ".").removesuffix(".py")
    lines = source.split("\n")
    line_offsets = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1  # +1 for newline

    # Classes
    for m in _PY_CLASS_RE.finditer(source):
        name = m.group(1)
        bases = m.group(2) or ""
        line_num = source[: m.start()].count("\n") + 1
        sig = f"class {name}{bases}"
        summary = _first_docstring_line(source, m.end())
        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=f"{module_name}.{name}",
            kind="class",
            signature=sig,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
            summary=summary,
        ))

    # Functions and methods
    for m in _PY_FUNC_RE.finditer(source):
        indent = m.group(1)
        name = m.group(2)
        params = m.group(3)
        ret = m.group(4)
        line_num = source[: m.start()].count("\n") + 1
        indent_level = len(indent)

        # Determine if this is a method (indented under a class)
        is_method = indent_level > 0

        # Find the enclosing class for methods
        enclosing_class = None
        if is_method:
            # Walk backwards from this position to find the nearest class at lower indent
            for sym in reversed(symbols):
                if sym.kind == "class" and sym.line_number < line_num:
                    enclosing_class = sym.name
                    break

        if name.startswith("_") and name != "__init__":
            continue  # skip private helpers

        ret_str = f" -> {ret.strip()}" if ret else ""
        sig = f"def {name}{params}{ret_str}"
        summary = _first_docstring_line(source, m.end())

        if is_method and enclosing_class:
            kind = "method"
            qualified = f"{module_name}.{enclosing_class}.{name}"
        else:
            kind = "function"
            qualified = f"{module_name}.{name}"

        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=qualified,
            kind=kind,
            signature=sig,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
            summary=summary,
        ))

    # Top-level UPPER_CASE assignments (constants)
    for m in _PY_ASSIGN_RE.finditer(source):
        name = m.group(1)
        line_num = source[: m.start()].count("\n") + 1
        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=f"{module_name}.{name}",
            kind="variable",
            signature=name,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
        ))

    return symbols


# ---------------------------------------------------------------------------
# TypeScript / JavaScript extraction
# ---------------------------------------------------------------------------

_TS_FUNCTION_RE = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*(<[^>]*>)?\s*(\([^)]*\))(?:\s*:\s*([^\n{]+))?",
    re.MULTILINE,
)
_TS_ARROW_CONST_RE = re.compile(
    r"^(?:export\s+)?(?:const|let)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?\(",
    re.MULTILINE,
)
_TS_CLASS_RE = re.compile(
    r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+(\w+))?",
    re.MULTILINE,
)
_TS_INTERFACE_RE = re.compile(
    r"^(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+(\w+))?",
    re.MULTILINE,
)
_TS_TYPE_RE = re.compile(
    r"^(?:export\s+)?type\s+(\w+)\s*(?:<[^>]*>)?\s*=",
    re.MULTILINE,
)
_JSDOC_RE = re.compile(r"/\*\*\s*(.*?)\*/", re.DOTALL)


def _preceding_jsdoc(source: str, pos: int) -> str:
    """Extract the first line of a JSDoc comment immediately preceding pos."""
    # Look at the ~300 chars before the match
    chunk = source[max(0, pos - 300) : pos]
    # Find the last JSDoc in this chunk
    matches = list(_JSDOC_RE.finditer(chunk))
    if not matches:
        return ""
    last = matches[-1]
    # Only use it if it ends near pos (within whitespace)
    between = chunk[last.end() :].strip()
    if between:
        return ""
    doc = last.group(1).strip()
    # Strip leading * from each line
    lines = [line.strip().lstrip("* ").strip() for line in doc.split("\n")]
    first = next((ln for ln in lines if ln and not ln.startswith("@")), "")
    return first[:120]


def extract_ts_symbols(source: str, rel_path: str) -> list[ExtractedSymbol]:
    symbols: list[ExtractedSymbol] = []
    module_name = rel_path.replace("/", ".")
    for sfx in (".ts", ".tsx", ".js", ".jsx"):
        module_name = module_name.removesuffix(sfx)

    # Functions
    for m in _TS_FUNCTION_RE.finditer(source):
        name = m.group(1)
        generics = m.group(2) or ""
        params = m.group(3)
        ret = m.group(4)
        line_num = source[: m.start()].count("\n") + 1
        ret_str = f": {ret.strip()}" if ret else ""
        sig = f"function {name}{generics}{params}{ret_str}"
        summary = _preceding_jsdoc(source, m.start())
        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=f"{module_name}.{name}",
            kind="function",
            signature=sig,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
            summary=summary,
        ))

    # Arrow function consts
    for m in _TS_ARROW_CONST_RE.finditer(source):
        name = m.group(1)
        line_num = source[: m.start()].count("\n") + 1
        sig = f"const {name} = (...) => ..."
        summary = _preceding_jsdoc(source, m.start())
        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=f"{module_name}.{name}",
            kind="function",
            signature=sig,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
            summary=summary,
        ))

    # Classes
    for m in _TS_CLASS_RE.finditer(source):
        name = m.group(1)
        extends = f" extends {m.group(2)}" if m.group(2) else ""
        line_num = source[: m.start()].count("\n") + 1
        sig = f"class {name}{extends}"
        summary = _preceding_jsdoc(source, m.start())
        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=f"{module_name}.{name}",
            kind="class",
            signature=sig,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
            summary=summary,
        ))

    # Interfaces
    for m in _TS_INTERFACE_RE.finditer(source):
        name = m.group(1)
        extends = f" extends {m.group(2)}" if m.group(2) else ""
        line_num = source[: m.start()].count("\n") + 1
        sig = f"interface {name}{extends}"
        summary = _preceding_jsdoc(source, m.start())
        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=f"{module_name}.{name}",
            kind="interface",
            signature=sig,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
            summary=summary,
        ))

    # Type aliases
    for m in _TS_TYPE_RE.finditer(source):
        name = m.group(1)
        line_num = source[: m.start()].count("\n") + 1
        sig = f"type {name} = ..."
        summary = _preceding_jsdoc(source, m.start())
        symbols.append(ExtractedSymbol(
            name=name,
            qualified_name=f"{module_name}.{name}",
            kind="type_alias",
            signature=sig,
            file_path=rel_path,
            line_number=line_num,
            byte_offset_start=m.start(),
            byte_offset_end=m.end(),
            summary=summary,
        ))

    return symbols


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, callable] = {
    ".py": extract_python_symbols,
    ".ts": extract_ts_symbols,
    ".tsx": extract_ts_symbols,
    ".js": extract_ts_symbols,
    ".jsx": extract_ts_symbols,
}

MAX_FILE_SIZE = 500 * 1024  # 500 KB


def extract_symbols_from_file(file_path: Path, project_root: Path) -> list[ExtractedSymbol]:
    """Extract symbols from a file, dispatching by extension.

    Returns an empty list for unsupported extensions or files that can't be read.
    """
    ext = file_path.suffix
    extractor = _EXTENSION_MAP.get(ext)
    if extractor is None:
        return []

    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            return []
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(project_root))
    return extractor(source, rel_path)
