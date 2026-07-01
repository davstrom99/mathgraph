"""Detect Python code symbols not attached to graph nodes."""

from __future__ import annotations

import ast
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path

from mathgraph_tool.loader import find_repo_root, load_graph
from mathgraph_tool.schema import GraphSpec


DEFAULT_EXCLUDES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
}


@dataclass(frozen=True)
class PythonSymbol:
    path: str
    symbol: str
    kind: str
    line: int

    @property
    def qualified(self) -> str:
        return f"{self.path}::{self.symbol}"


@dataclass(frozen=True)
class OrphanReport:
    scanned: list[PythonSymbol]
    attached: set[tuple[str, str]]
    orphans: list[PythonSymbol]

    @property
    def passed(self) -> bool:
        return not self.orphans


def find_orphans(
    graph: GraphSpec | None = None,
    *,
    repo_root: Path | None = None,
    roots: list[str] | None = None,
    excludes: list[str] | None = None,
    include_private: bool = False,
) -> OrphanReport:
    root = (repo_root or find_repo_root()).resolve()
    graph = graph or load_graph(repo_root=root)
    root_values = roots or graph.project.code_roots or _existing_default_roots(root)
    exclude_values = set(excludes or []) | set(graph.project.code_exclude) | DEFAULT_EXCLUDES

    symbols: list[PythonSymbol] = []
    for root_value in root_values:
        target = root / root_value
        if target.is_file() and target.suffix == ".py":
            if not _is_excluded(target.relative_to(root), exclude_values):
                symbols.extend(_python_symbols(target, root, include_private=include_private))
        elif target.is_dir():
            for path in sorted(target.rglob("*.py")):
                relative = path.relative_to(root)
                if _is_excluded(relative, exclude_values):
                    continue
                symbols.extend(_python_symbols(path, root, include_private=include_private))

    attached = {
        (ref.path.replace("\\", "/"), ref.symbol)
        for _, ref in graph.all_code_refs()
        if ref.symbol
    }
    orphans = [
        symbol
        for symbol in symbols
        if (symbol.path, symbol.symbol) not in attached
    ]
    return OrphanReport(scanned=symbols, attached=attached, orphans=orphans)


def format_orphan_report(report: OrphanReport, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(
            {
                "scanned": [symbol.__dict__ for symbol in report.scanned],
                "orphans": [symbol.__dict__ for symbol in report.orphans],
            },
            indent=2,
        )

    lines = [
        f"Scanned Python symbols: {len(report.scanned)}",
        f"Attached Python symbols: {len(report.attached)}",
        f"Orphan Python symbols: {len(report.orphans)}",
    ]
    if report.orphans:
        lines.append("")
        lines.append("Orphans:")
        lines.extend(f"- {symbol.qualified} (line {symbol.line}, {symbol.kind})" for symbol in report.orphans)
    return "\n".join(lines)


def _existing_default_roots(root: Path) -> list[str]:
    candidates = ["src", "experiments", "tests"]
    return [candidate for candidate in candidates if (root / candidate).exists()]


def _is_excluded(relative: Path, excludes: set[str]) -> bool:
    path_text = relative.as_posix()
    for pattern in excludes:
        normalized = pattern.replace("\\", "/")
        if any(fnmatch.fnmatch(part, normalized) for part in relative.parts):
            return True
        if fnmatch.fnmatch(path_text, normalized):
            return True
    return False


def _python_symbols(path: Path, root: Path, *, include_private: bool) -> list[PythonSymbol]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []

    relative = path.relative_to(root).as_posix()
    symbols: list[PythonSymbol] = []
    for item in tree.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            if _include_symbol(item.name, include_private=include_private):
                symbols.append(PythonSymbol(relative, item.name, "function", item.lineno))
        elif isinstance(item, ast.ClassDef):
            if _include_symbol(item.name, include_private=include_private):
                symbols.append(PythonSymbol(relative, item.name, "class", item.lineno))
    return symbols


def _include_symbol(name: str, *, include_private: bool) -> bool:
    if include_private:
        return True
    return not name.startswith("_")
