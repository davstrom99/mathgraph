"""Consistency checks for mathgraph specs."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from mathgraph_tool.loader import DEFAULT_GRAPH_PATH, find_repo_root, load_graph
from mathgraph_tool.indexing import INDEX_PATH, check_index, indexed_line_exists, load_index
from mathgraph_tool.schema import CodeRef, GraphSpec, Node, NodeKind, TexRef


@dataclass
class CheckResult:
    graph: GraphSpec | None = None
    ok: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def run_checks(graph_path: str | Path = DEFAULT_GRAPH_PATH, repo_root: Path | None = None) -> CheckResult:
    root = (repo_root or find_repo_root()).resolve()
    result = CheckResult()

    try:
        graph = load_graph(graph_path, repo_root=root)
    except ValidationError as exc:
        result.errors.append(f"schema validation failed: {exc}")
        return result
    except Exception as exc:
        result.errors.append(f"could not load graph: {exc}")
        return result

    result.graph = graph
    result.ok.append(f"loaded {len(graph.nodes)} nodes and {len(graph.edges)} edges")
    result.ok.append("all node ids are unique")
    result.ok.append("all edge endpoints exist")
    result.ok.append("all node and edge kinds are recognized")

    _check_graph_invariants(graph, result)
    _check_tex_root(root, graph, result)
    _check_tex_refs(root, graph, result)
    _check_code_refs(root, graph, result)
    _check_outputs(root, graph, result)
    _check_init_index(root, graph, result)

    return result


GREEK_ALIASES = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "pi": "π",
    "sigma": "σ",
    "tau": "τ",
    "theta": "θ",
}

IGNORED_PARSE_TOKENS = {
    "R",
    "S",
    "I",
    "N",
    "MAP",
    "StudentT",
}


def _check_graph_invariants(graph: GraphSpec, result: CheckResult) -> None:
    incoming = _incoming_by_node(graph)
    variable_nodes = {node.id: node for node in graph.nodes if node.kind == NodeKind.VARIABLE}
    alias_to_variable = _variable_aliases(variable_nodes.values())
    errors: list[str] = []

    for node in graph.nodes:
        incoming_edges = incoming.get(node.id, [])
        if node.kind != NodeKind.VARIABLE and not incoming_edges:
            errors.append(
                f"non-variable node has no incoming dependencies: {node.id}"
            )

        if node.kind == NodeKind.VARIABLE:
            if node.uses:
                errors.append(f"variable node must not declare uses: {node.id}")
            continue

        used_variables, unresolved = _declared_or_parsed_variable_uses(node, alias_to_variable)
        for item in unresolved:
            errors.append(f"{node.id} uses undefined variable symbol: {item}")

        upstream = _upstream_node_ids(node.id, incoming)
        for variable_id in sorted(used_variables):
            if variable_id not in upstream:
                errors.append(
                    f"{node.id} uses {variable_id}, but that variable is not upstream"
                )

    if errors:
        result.errors.extend(f"graph invariant violation: {error}" for error in errors)
    else:
        result.ok.append("graph invariants hold: variables are primitive and all declared variable uses are upstream")


def _incoming_by_node(graph: GraphSpec) -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        incoming.setdefault(edge.to, []).append(edge.from_)
    return incoming


def _upstream_node_ids(node_id: str, incoming: dict[str, list[str]]) -> set[str]:
    upstream: set[str] = set()
    stack = list(incoming.get(node_id, []))
    while stack:
        current = stack.pop()
        if current in upstream:
            continue
        upstream.add(current)
        stack.extend(incoming.get(current, []))
    return upstream


def _variable_aliases(variable_nodes: Iterable[Node]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in variable_nodes:
        candidates = {node.id, node.id.split(".")[-1]}
        if node.symbol:
            candidates.update(_symbol_aliases(node.symbol))
        for candidate in candidates:
            normalized = _normalize_symbol(candidate)
            if normalized:
                aliases[normalized] = node.id
    return aliases


def _symbol_aliases(symbol: str) -> set[str]:
    aliases = {symbol}
    normalized = _normalize_symbol(symbol)
    if normalized:
        aliases.add(normalized)
    if normalized in GREEK_ALIASES:
        aliases.add(GREEK_ALIASES[normalized])
    for name, glyph in GREEK_ALIASES.items():
        if glyph == symbol:
            aliases.add(name)
            aliases.add(f"\\{name}")
    return aliases


def _declared_or_parsed_variable_uses(
    node: Node, alias_to_variable: dict[str, str]
) -> tuple[set[str], list[str]]:
    if node.uses is not None:
        uses = node.uses
    else:
        uses = _parse_statement_symbols(node.statement)

    resolved: set[str] = set()
    unresolved: list[str] = []
    for item in uses:
        normalized = _normalize_symbol(item)
        variable_id = alias_to_variable.get(normalized)
        if variable_id is None:
            unresolved.append(item)
        else:
            resolved.add(variable_id)
    return resolved, unresolved


def _parse_statement_symbols(statement: str) -> list[str]:
    symbols: list[str] = []
    symbols.extend(re.findall(r"\\([A-Za-z]+)", statement))
    symbols.extend(re.findall(r"[α-ωΑ-Ω]", statement))
    symbols.extend(re.findall(r"\b[A-Za-z](?:_[A-Za-z0-9]+)?\b", statement))
    symbols.extend(
        token
        for token in re.findall(r"\b(?:alpha|beta|gamma|delta|epsilon|lambda|mu|nu|pi|sigma|tau|theta)\b", statement)
    )
    unique: list[str] = []
    for symbol in symbols:
        if symbol in IGNORED_PARSE_TOKENS:
            continue
        if symbol not in unique:
            unique.append(symbol)
    return unique


def _normalize_symbol(symbol: str) -> str:
    value = symbol.strip()
    if not value:
        return ""
    if value.startswith("\\"):
        value = value[1:]
    value = value.replace("{", "").replace("}", "")
    value = value.replace("^", "").replace(" ", "")
    value = value.replace("_", "_")
    return value


def _check_tex_root(root: Path, graph: GraphSpec, result: CheckResult) -> None:
    tex_root = root / graph.project.tex_root
    if tex_root.exists():
        result.ok.append(f"project TeX root exists: {graph.project.tex_root}")
    else:
        result.errors.append(f"project TeX root does not exist: {graph.project.tex_root}")


def _check_tex_refs(root: Path, graph: GraphSpec, result: CheckResult) -> None:
    missing_files: list[str] = []
    missing_labels: list[str] = []
    contents: dict[Path, str] = {}
    project_tex = root / graph.project.tex_root
    if project_tex.exists():
        contents[project_tex] = project_tex.read_text(encoding="utf-8")

    for owner, ref in graph.all_tex_refs():
        tex_path = root / ref.file
        if not tex_path.exists():
            missing_files.append(f"{owner}: {ref.file}")
            continue
        text = contents.setdefault(tex_path, tex_path.read_text(encoding="utf-8"))
        if ref.label not in text:
            missing_labels.append(f"{owner}: {ref.file}#{ref.label}")

    if missing_files:
        result.errors.extend(f"TeX file missing: {item}" for item in missing_files)
    else:
        result.ok.append("all TeX files exist")

    if missing_labels:
        result.errors.extend(f"TeX label missing: {item}" for item in missing_labels)
    else:
        result.ok.append("all referenced TeX labels exist")

    derivations_by_file: dict[str, set[str]] = {}
    for edge in graph.edges:
        derivations_by_file.setdefault(edge.tex.file, set()).add(edge.tex.label)
    aggregate_files = {
        file: labels for file, labels in derivations_by_file.items() if len(labels) > 1
    }
    if aggregate_files:
        for file, labels in sorted(aggregate_files.items()):
            result.errors.append(
                "derivation file contains multiple referenced derivations: "
                f"{file} ({', '.join(sorted(labels))})"
            )
    else:
        result.ok.append("each distinct referenced derivation has a standalone TeX file")

    duplicate_equation_labels: list[str] = []
    for path, text in contents.items():
        for environment in re.finditer(
            r"\\begin\{(equation|align|gather|multline)\*?\}(.*?)\\end\{\1\*?\}",
            text,
            flags=re.DOTALL,
        ):
            labels = re.findall(r"\\label\{([^}]+)\}", environment.group(2))
            if len(labels) > 1:
                duplicate_equation_labels.append(f"{path.relative_to(root).as_posix()}: {', '.join(labels)}")
    if duplicate_equation_labels:
        result.errors.extend(f"amsmath equation has multiple labels: {item}" for item in duplicate_equation_labels)
    else:
        result.ok.append("amsmath equations use at most one canonical label")


def _check_code_refs(root: Path, graph: GraphSpec, result: CheckResult) -> None:
    missing_paths: list[str] = []
    missing_symbols: list[str] = []
    syntax_errors: list[str] = []
    invalid_lines: list[str] = []
    symbol_cache: dict[Path, set[str]] = {}
    line_count_cache: dict[Path, int] = {}

    for owner, ref in graph.all_code_refs():
        code_path = root / ref.path
        if not code_path.exists():
            missing_paths.append(f"{owner}: {ref.path}")
            continue
        if ref.line is not None:
            line_count = line_count_cache.setdefault(
                code_path, len(code_path.read_text(encoding="utf-8").splitlines())
            )
            if ref.line > line_count:
                invalid_lines.append(
                    f"{owner}: {ref.path}:{ref.line} (file has {line_count} lines)"
                )
        if ref.symbol is None:
            continue
        try:
            symbols = symbol_cache.setdefault(code_path, _python_symbols(code_path))
        except SyntaxError as exc:
            syntax_errors.append(f"{ref.path}: {exc}")
            continue
        if ref.symbol not in symbols:
            missing_symbols.append(f"{owner}: {ref.path}::{ref.symbol}")

    if missing_paths:
        result.errors.extend(f"code path missing: {item}" for item in missing_paths)
    else:
        result.ok.append("all code paths exist")

    if syntax_errors:
        result.errors.extend(f"Python syntax error: {item}" for item in syntax_errors)

    if invalid_lines:
        result.errors.extend(f"code line missing: {item}" for item in invalid_lines)
    else:
        result.ok.append("all referenced code lines exist")

    if missing_symbols:
        result.errors.extend(f"Python symbol missing: {item}" for item in missing_symbols)
    elif not syntax_errors:
        result.ok.append("all referenced Python symbols exist")


def _python_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.add(node.target.id)
    return symbols


def _check_outputs(root: Path, graph: GraphSpec, result: CheckResult) -> None:
    missing_parents: list[str] = []
    missing_outputs: list[str] = []

    for node in graph.nodes:
        for output in node.outputs:
            path = root / output.path
            if not path.parent.exists():
                missing_parents.append(f"node {node.id}: {output.path}")
            elif not path.exists():
                missing_outputs.append(f"node {node.id}: {output.path}")

    if missing_parents:
        result.errors.extend(f"output parent directory missing: {item}" for item in missing_parents)
    else:
        result.ok.append("all declared output parent directories exist")

    result.warnings.extend(f"declared output does not exist yet: {item}" for item in missing_outputs)


def _check_init_index(root: Path, graph: GraphSpec, result: CheckResult) -> None:
    if not (root / INDEX_PATH).exists():
        return
    index_result = check_index(root)
    result.ok.extend(index_result.ok)
    result.warnings.extend(index_result.warnings)
    result.errors.extend(f"initialization index: {item}" for item in index_result.errors)
    if index_result.errors:
        return

    try:
        _, records = load_index(root)
    except ValueError as exc:
        result.errors.append(f"initialization index: {exc}")
        return
    missing: list[str] = []
    for owner, ref in graph.all_code_refs():
        if ref.line is not None and not indexed_line_exists(records, ref.path, ref.line):
            missing.append(f"{owner}: {ref.path}:{ref.line}")
    if missing:
        result.errors.extend(f"code reference is outside indexed evidence: {item}" for item in missing)
    else:
        result.ok.append("all exact-line code references resolve inside indexed evidence")


def format_check_result(result: CheckResult) -> str:
    lines: list[str] = []

    for item in result.ok:
        lines.append(f"OK: {item}.")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)

    if result.errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in result.errors)

    return "\n".join(lines)


def assert_graph_references_valid(graph_path: str | Path = DEFAULT_GRAPH_PATH, repo_root: Path | None = None) -> CheckResult:
    result = run_checks(graph_path, repo_root=repo_root)
    if not result.passed:
        raise AssertionError(format_check_result(result))
    return result
