from mathgraph_tool.checks import format_check_result, run_checks


def test_mathgraph_check_has_no_errors():
    result = run_checks()

    assert result.passed, format_check_result(result)
    assert result.graph is not None
    assert len(result.graph.nodes) == 26
    assert len(result.graph.edges) == 31


def test_non_variable_nodes_must_have_incoming_dependencies(tmp_path):
    _write_minimal_tex(tmp_path)
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project:
  id: bad
  title: Bad Graph
  tex_root: paper/main.tex

nodes:
  - id: var.x
    kind: variable
    title: Variable x
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
  - id: model.bad
    kind: assumption
    title: Bad primitive assumption
    statement: "x has a property."
    uses: [var.x]
    tex: {file: paper/main.tex, label: model:bad}

edges: []
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert not result.passed
    assert "non-variable node has no incoming dependencies: model.bad" in format_check_result(result)


def test_undefined_variable_uses_are_reported(tmp_path):
    _write_minimal_tex(tmp_path)
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project:
  id: bad
  title: Bad Graph
  tex_root: paper/main.tex

nodes:
  - id: var.x
    kind: variable
    title: Variable x
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
  - id: model.bad
    kind: assumption
    title: Bad assumption
    statement: "z = x."
    uses: [z]
    tex: {file: paper/main.tex, label: model:bad}

edges:
  - from: var.x
    to: model.bad
    kind: defines
    description: "x specifies the bad model."
    tex: {file: paper/main.tex, label: edge:x-to-bad}
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert not result.passed
    assert "model.bad uses undefined variable symbol: z" in format_check_result(result)


def test_statement_parser_finds_variable_used_before_definition(tmp_path):
    _write_minimal_tex(tmp_path)
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project:
  id: bad
  title: Bad Graph
  tex_root: paper/main.tex

nodes:
  - id: var.x
    kind: variable
    title: Variable x
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
  - id: var.z
    kind: variable
    title: Variable z
    symbol: z
    statement: "z in R."
    tex: {file: paper/main.tex, label: def:z}
  - id: model.bad
    kind: assumption
    title: Bad assumption
    statement: "z = x."
    tex: {file: paper/main.tex, label: model:bad}

edges:
  - from: var.x
    to: model.bad
    kind: defines
    description: "x specifies the bad model."
    tex: {file: paper/main.tex, label: edge:x-to-bad}
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert not result.passed
    assert "model.bad uses var.z, but that variable is not upstream" in format_check_result(result)


def test_statement_parser_reports_unknown_symbol_without_uses(tmp_path):
    _write_minimal_tex(tmp_path)
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project:
  id: bad
  title: Bad Graph
  tex_root: paper/main.tex

nodes:
  - id: var.x
    kind: variable
    title: Variable x
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
  - id: model.bad
    kind: assumption
    title: Bad assumption
    statement: "z = x."
    tex: {file: paper/main.tex, label: model:bad}

edges:
  - from: var.x
    to: model.bad
    kind: defines
    description: "x specifies the bad model."
    tex: {file: paper/main.tex, label: edge:x-to-bad}
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert not result.passed
    assert "model.bad uses undefined variable symbol: z" in format_check_result(result)


def test_replaces_edge_kind_is_not_allowed(tmp_path):
    _write_minimal_tex(tmp_path)
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project:
  id: bad
  title: Bad Graph
  tex_root: paper/main.tex

nodes:
  - id: var.x
    kind: variable
    title: Variable x
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
  - id: model.a
    kind: assumption
    title: Model A
    statement: "x has property A."
    uses: [var.x]
    tex: {file: paper/main.tex, label: model:bad}
  - id: model.b
    kind: assumption
    title: Model B
    statement: "x has property B."
    uses: [var.x]
    tex: {file: paper/main.tex, label: model:bad}

edges:
  - from: var.x
    to: model.a
    kind: defines
    description: "x specifies model A."
    tex: {file: paper/main.tex, label: edge:x-to-bad}
  - from: var.x
    to: model.b
    kind: defines
    description: "x specifies model B."
    tex: {file: paper/main.tex, label: edge:x-to-bad}
  - from: model.a
    to: model.b
    kind: replaces
    description: "Disallowed replacement edge."
    tex: {file: paper/main.tex, label: edge:x-to-bad}
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert not result.passed
    assert "schema validation failed" in format_check_result(result)
    assert "replaces" in format_check_result(result)


def test_code_line_reference_must_exist(tmp_path):
    _write_minimal_tex(tmp_path)
    (tmp_path / "model.py").write_text("x = 1\n", encoding="utf-8")
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project:
  id: bad
  title: Bad Graph
  tex_root: paper/main.tex

nodes:
  - id: var.x
    kind: variable
    title: "x in R"
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
    code:
      - {path: model.py, line: 2}

edges: []
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert not result.passed
    assert "code line missing: node var.x: model.py:2" in format_check_result(result)


def test_derivation_file_must_not_collect_distinct_derivations(tmp_path):
    _write_minimal_tex(tmp_path)
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project:
  id: bad
  title: Bad Graph
  tex_root: paper/main.tex

nodes:
  - id: var.x
    kind: variable
    title: "x in R"
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
  - id: model.a
    kind: assumption
    title: Model A
    statement: "x has property A."
    uses: [var.x]
    tex: {file: paper/main.tex, label: model:bad}
  - id: model.b
    kind: assumption
    title: Model B
    statement: "x has property B."
    uses: [var.x]
    tex: {file: paper/main.tex, label: model:bad}

edges:
  - from: var.x
    to: model.a
    kind: defines
    description: "x specifies model A."
    tex: {file: paper/main.tex, label: edge:x-to-bad}
  - from: var.x
    to: model.b
    kind: defines
    description: "x specifies model B."
    tex: {file: paper/main.tex, label: edge:x-to-other}
""",
        encoding="utf-8",
    )
    with (tmp_path / "paper/main.tex").open("a", encoding="utf-8") as tex:
        tex.write("\\label{edge:x-to-other}\n")

    result = run_checks(graph_path, repo_root=tmp_path)

    assert not result.passed
    assert "derivation file contains multiple referenced derivations" in format_check_result(result)


def test_multiple_edges_may_share_one_derivation(tmp_path):
    _write_minimal_tex(tmp_path)
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project: {id: shared, title: Shared, tex_root: paper/main.tex}
nodes:
  - {id: var.x, kind: variable, title: "x in R", symbol: x, statement: "x in R.", tex: {file: paper/main.tex, label: "def:x"}}
  - {id: model.a, kind: assumption, title: A, statement: A, uses: [var.x], tex: {file: paper/main.tex, label: "model:bad"}}
  - {id: model.b, kind: assumption, title: B, statement: B, uses: [var.x], tex: {file: paper/main.tex, label: "model:bad"}}
edges:
  - {from: var.x, to: model.a, kind: defines, description: shared, tex: {file: paper/main.tex, label: "edge:x-to-bad"}}
  - {from: var.x, to: model.b, kind: defines, description: shared, tex: {file: paper/main.tex, label: "edge:x-to-bad"}}
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert result.passed, format_check_result(result)


def test_amsmath_equation_rejects_multiple_labels(tmp_path):
    _write_minimal_tex(tmp_path)
    with (tmp_path / "paper/main.tex").open("a", encoding="utf-8") as tex:
        tex.write("\\begin{equation}x=1\\label{eq:one}\\label{eq:two}\\end{equation}\n")
    graph_path = tmp_path / "mathgraph" / "graph.yaml"
    graph_path.parent.mkdir()
    graph_path.write_text(
        """
project: {id: labels, title: Labels, tex_root: paper/main.tex}
nodes: []
edges: []
""",
        encoding="utf-8",
    )

    result = run_checks(graph_path, repo_root=tmp_path)

    assert "amsmath equation has multiple labels" in format_check_result(result)


def _write_minimal_tex(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text(
        """
\\section{Definitions}
\\label{def:x}
\\label{def:z}
\\label{model:bad}
\\label{edge:x-to-bad}
""",
        encoding="utf-8",
    )
