from pathlib import Path

from mathgraph_tool.checks import assert_graph_references_valid


def test_graph_references_are_valid():
    result = assert_graph_references_valid()

    assert result.graph is not None
    assert all((Path.cwd() / ref.file).exists() for _, ref in result.graph.all_tex_refs())
    assert all((Path.cwd() / ref.path).exists() for _, ref in result.graph.all_code_refs())

