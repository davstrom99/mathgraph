"""YAML loading for mathgraph specs."""

from __future__ import annotations

from pathlib import Path

import yaml

from mathgraph_tool.schema import GraphSpec


DEFAULT_GRAPH_PATH = Path("mathgraph/graph.yaml")


def find_repo_root(start: Path | None = None) -> Path:
    """Find the repository root by walking upward to `mathgraph/graph.yaml`."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / DEFAULT_GRAPH_PATH).exists():
            return candidate
    return current


def load_graph(path: str | Path = DEFAULT_GRAPH_PATH, repo_root: Path | None = None) -> GraphSpec:
    root = (repo_root or find_repo_root()).resolve()
    graph_path = Path(path)
    if not graph_path.is_absolute():
        graph_path = root / graph_path
    with graph_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{graph_path} must contain a YAML mapping")
    return GraphSpec.model_validate(data)

