"""Human-readable graph navigation and coverage reports."""

from __future__ import annotations

import ast
from collections import defaultdict, deque
from pathlib import Path
from typing import Iterable

import networkx as nx

from mathgraph_tool.loader import find_repo_root, load_graph
from mathgraph_tool.orphans import find_orphans
from mathgraph_tool.schema import CodeRef, Edge, GraphSpec, Node, NodeKind


MATH_NODE_KINDS = {
    NodeKind.VARIABLE,
    NodeKind.ASSUMPTION,
    NodeKind.OBJECTIVE,
    NodeKind.ESTIMATOR,
    NodeKind.APPROXIMATION,
    NodeKind.SIMULATOR,
    NodeKind.VALIDATION,
}

IMPLEMENTATION_RELEVANT_KINDS = {
    NodeKind.ASSUMPTION,
    NodeKind.OBJECTIVE,
    NodeKind.ESTIMATOR,
    NodeKind.APPROXIMATION,
    NodeKind.SIMULATOR,
    NodeKind.VALIDATION,
    NodeKind.EXPERIMENT,
}


def build_digraph(graph: GraphSpec) -> nx.MultiDiGraph:
    directed = nx.MultiDiGraph()
    for node in graph.nodes:
        directed.add_node(node.id, node=node)
    for index, edge in enumerate(graph.edges):
        directed.add_edge(edge.from_, edge.to, key=index, edge=edge)
    return directed


def format_node_card(node_id: str, graph: GraphSpec | None = None) -> str:
    graph = graph or load_graph()
    node = _node(graph, node_id)
    incoming = [edge for edge in graph.edges if edge.to == node_id]
    outgoing = [edge for edge in graph.edges if edge.from_ == node_id]

    lines = [
        f"Node: {node.id}",
        f"Kind: {node.kind.value}",
        f"Title: {node.title}",
        "Statement:",
        f"  {node.statement}",
        "",
        "Variable uses:",
    ]
    lines.extend(_format_string_list(node.uses or []))
    lines.extend([
        "",
        "TeX:",
    ])
    lines.extend(_format_tex_ref(node.tex))
    lines.append("")
    lines.append("Code:")
    lines.extend(_format_code_refs(node.code))
    lines.append("")
    lines.append("Outputs:")
    lines.extend(_format_outputs(node))
    lines.append("")
    lines.append("Incoming edges:")
    lines.extend(_format_edge_list(incoming))
    lines.append("")
    lines.append("Outgoing edges:")
    lines.extend(_format_edge_list(outgoing))
    return "\n".join(lines)


def format_impact_report(node_id: str, graph: GraphSpec | None = None, verbose: bool = False) -> str:
    graph = graph or load_graph()
    _node(graph, node_id)
    paths = downstream_paths(graph, node_id)
    reachable_ids = list(paths)
    reachable_nodes = [_node(graph, affected_id) for affected_id in reachable_ids]

    math_nodes = [node for node in reachable_nodes if node.kind in MATH_NODE_KINDS]
    experiments = [node for node in reachable_nodes if node.kind == NodeKind.EXPERIMENT]
    code_refs = _dedupe_refs(
        ref
        for node in reachable_nodes
        for ref in node.code
        if not _is_test_ref(ref) and not _is_experiment_ref(ref, node)
    )
    test_refs = _dedupe_refs(
        ref for node in reachable_nodes for ref in node.code if _is_test_ref(ref)
    )
    experiment_refs = _dedupe_refs(
        ref for node in experiments for ref in node.code if _is_experiment_ref(ref, node)
    )
    outputs = _dedupe_strings(output.path for node in reachable_nodes for output in node.outputs)

    lines = [f"Impact from: {node_id}", ""]
    lines.append("Affected mathematical nodes:")
    lines.extend(_format_nodes(math_nodes))
    lines.append("")
    lines.append("Affected code symbols:")
    lines.extend(_format_refs(code_refs))
    lines.append("")
    lines.append("Affected tests:")
    lines.extend(_format_refs(test_refs))
    lines.append("")
    lines.append("Affected experiments:")
    if experiments:
        for node in experiments:
            lines.append(f"- {node.id} ({node.title})")
        for ref in experiment_refs:
            lines.append(f"- {_format_code_ref(ref)}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Affected outputs:")
    lines.extend(_format_string_list(outputs))

    if verbose:
        lines.append("")
        lines.append("Edge paths:")
        if not paths:
            lines.append("- none")
        for target_id, path in paths.items():
            lines.append(f"- {target_id}")
            for edge in path:
                lines.append(
                    f"  {edge.from_} --{edge.kind.value}--> {edge.to}"
                    f" [{edge.tex.file}#{edge.tex.label}]"
                )
                lines.append(f"    {edge.description}")

    return "\n".join(lines)


def downstream_paths(graph: GraphSpec, node_id: str) -> dict[str, list[Edge]]:
    adjacency: dict[str, list[Edge]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[edge.from_].append(edge)

    paths: dict[str, list[Edge]] = {}
    queue: deque[str] = deque([node_id])
    seen = {node_id}
    while queue:
        current = queue.popleft()
        for edge in adjacency.get(current, []):
            if edge.to in seen:
                continue
            seen.add(edge.to)
            paths[edge.to] = [*paths.get(current, []), edge]
            queue.append(edge.to)
    return paths


def format_coverage_report(graph: GraphSpec | None = None, repo_root: Path | None = None) -> str:
    graph = graph or load_graph()
    root = (repo_root or find_repo_root()).resolve()

    node_tex_count = sum(1 for node in graph.nodes if node.tex is not None)
    edge_tex_count = sum(1 for edge in graph.edges if edge.tex is not None)
    code_nodes = [node for node in graph.nodes if node.code]
    implementation_nodes = [node for node in graph.nodes if node.kind in IMPLEMENTATION_RELEVANT_KINDS]
    implemented_relevant = [node for node in implementation_nodes if node.code]
    estimators = [node for node in graph.nodes if node.kind == NodeKind.ESTIMATOR]
    validated_estimators = [
        node for node in estimators if any(_node(graph, target).kind == NodeKind.VALIDATION for target in downstream_paths(graph, node.id))
    ]
    experiments = [node for node in graph.nodes if node.kind == NodeKind.EXPERIMENT]
    experiments_with_outputs = [node for node in experiments if node.outputs]
    unimplemented = [node for node in implementation_nodes if not node.code]
    suspicious = suspicious_code_references(graph, root)
    orphan_report = find_orphans(graph, repo_root=root)

    lines = [
        f"Nodes: {len(graph.nodes)}",
        f"Edges: {len(graph.edges)}",
        "",
        "TeX coverage:",
        f"- nodes with TeX references: {node_tex_count}/{len(graph.nodes)}",
        f"- edges with TeX derivation references: {edge_tex_count}/{len(graph.edges)}",
        "",
        "Implementation coverage:",
        f"- nodes with code references: {len(code_nodes)}/{len(graph.nodes)}",
        f"- implementation-relevant nodes with code references: {len(implemented_relevant)}/{len(implementation_nodes)}",
        f"- estimators with implementation: {_count_with_code(graph, NodeKind.ESTIMATOR)}",
        f"- assumptions with implementation: {_count_with_code(graph, NodeKind.ASSUMPTION)}",
        f"- simulators with implementation: {_count_with_code(graph, NodeKind.SIMULATOR)}",
        "",
        "Validation coverage:",
        f"- estimators connected to validation: {len(validated_estimators)}/{len(estimators)}",
        f"- experiments with outputs declared: {len(experiments_with_outputs)}/{len(experiments)}",
        "",
        "Unimplemented mathematical nodes:",
    ]
    lines.extend(_format_nodes(unimplemented))
    lines.append("")
    lines.append("Orphan or suspicious references:")
    lines.extend(_format_string_list(suspicious))
    lines.append("")
    lines.append("Orphan code symbols:")
    if orphan_report.orphans:
        lines.extend(_format_string_list(symbol.qualified for symbol in orphan_report.orphans))
    else:
        lines.append("- none")
    return "\n".join(lines)


def suspicious_code_references(graph: GraphSpec, repo_root: Path) -> list[str]:
    suspicious: list[str] = []
    for node in graph.nodes:
        for ref in node.code:
            path = repo_root / ref.path
            if ref.symbol and path.exists() and _symbol_raises_not_implemented(path, ref.symbol):
                suspicious.append(
                    f"{node.id}: {_format_code_ref(ref)} raises NotImplementedError"
                )
    return suspicious


def _symbol_raises_not_implemented(path: Path, symbol: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for item in tree.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and item.name == symbol:
            return any(_is_not_implemented_raise(node) for node in ast.walk(item))
    return False


def _is_not_implemented_raise(node: ast.AST) -> bool:
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    exc = node.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"


def _node(graph: GraphSpec, node_id: str) -> Node:
    try:
        return graph.node_by_id[node_id]
    except KeyError as exc:
        raise ValueError(f"unknown node id: {node_id}") from exc


def _format_tex_ref(tex) -> list[str]:
    if tex is None:
        return ["  none"]
    return [f"  {tex.file}#{tex.label}"]


def _format_code_refs(refs: Iterable[CodeRef]) -> list[str]:
    items = [_format_code_ref(ref) for ref in refs]
    return _format_string_list(items)


def _format_code_ref(ref: CodeRef) -> str:
    value = f"{ref.path}::{ref.symbol}" if ref.symbol else ref.path
    if ref.line is not None:
        value += f":{ref.line}"
    return value


def _format_refs(refs: Iterable[CodeRef]) -> list[str]:
    return _format_string_list(_format_code_ref(ref) for ref in refs)


def _format_outputs(node: Node) -> list[str]:
    return _format_string_list(output.path for output in node.outputs)


def _format_edge_list(edges: Iterable[Edge]) -> list[str]:
    lines: list[str] = []
    for edge in edges:
        lines.append(f"  {edge.from_} --{edge.kind.value}--> {edge.to}")
        lines.append(f"    {edge.description}")
        lines.append(f"    TeX: {edge.tex.file}#{edge.tex.label}")
    return lines or ["  none"]


def _format_nodes(nodes: Iterable[Node]) -> list[str]:
    items = [f"{node.id} ({node.kind.value}: {node.title})" for node in nodes]
    return _format_string_list(items)


def _format_string_list(items: Iterable[str]) -> list[str]:
    values = list(items)
    if not values:
        return ["- none"]
    return [f"- {item}" for item in values]


def _dedupe_refs(refs: Iterable[CodeRef]) -> list[CodeRef]:
    seen: set[tuple[str, str | None, int | None]] = set()
    unique: list[CodeRef] = []
    for ref in refs:
        key = (ref.path, ref.symbol, ref.line)
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


def _dedupe_strings(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _is_test_ref(ref: CodeRef) -> bool:
    normalized = ref.path.replace("\\", "/")
    return normalized.startswith("tests/") or "/tests/" in f"/{normalized}"


def _is_experiment_ref(ref: CodeRef, node: Node) -> bool:
    normalized = ref.path.replace("\\", "/")
    return (
        node.kind == NodeKind.EXPERIMENT
        or normalized.startswith("experiments/")
        or "/experiments/" in f"/{normalized}"
    )


def _count_with_code(graph: GraphSpec, *kinds: NodeKind) -> str:
    nodes = [node for node in graph.nodes if node.kind in kinds]
    with_code = [node for node in nodes if node.code]
    return f"{len(with_code)}/{len(nodes)}"
