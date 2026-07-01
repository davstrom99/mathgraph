from pathlib import Path

from mathgraph_tool.orphans import find_orphans, format_orphan_report


def test_orphans_report_unattached_public_symbols(tmp_path):
    _write_graph(tmp_path, code_refs=[])
    _write(tmp_path / "src/model.py", "def attached():\n    pass\n\ndef missing():\n    pass\n\nclass Model:\n    pass\n")

    report = find_orphans(repo_root=tmp_path)

    assert {symbol.symbol for symbol in report.orphans} == {"attached", "missing", "Model"}
    text = format_orphan_report(report)
    assert "src/model.py::missing" in text


def test_orphans_ignore_graph_attached_symbols(tmp_path):
    _write_graph(tmp_path, code_refs=["src/model.py::attached"])
    _write(tmp_path / "src/model.py", "def attached():\n    pass\n\ndef missing():\n    pass\n")

    report = find_orphans(repo_root=tmp_path)

    assert {symbol.symbol for symbol in report.orphans} == {"missing"}


def test_orphans_ignore_private_by_default_and_include_with_flag(tmp_path):
    _write_graph(tmp_path, code_refs=[])
    _write(tmp_path / "src/model.py", "def _helper():\n    pass\n")

    default_report = find_orphans(repo_root=tmp_path)
    private_report = find_orphans(repo_root=tmp_path, include_private=True)

    assert default_report.orphans == []
    assert [symbol.symbol for symbol in private_report.orphans] == ["_helper"]


def test_orphans_detect_test_functions_and_json_output(tmp_path):
    _write_graph(tmp_path, code_refs=["tests/test_model.py::test_attached"])
    _write(tmp_path / "tests/test_model.py", "def test_attached():\n    pass\n\ndef test_missing():\n    pass\n")

    report = find_orphans(repo_root=tmp_path)
    json_text = format_orphan_report(report, as_json=True)

    assert [symbol.symbol for symbol in report.orphans] == ["test_missing"]
    assert '"symbol": "test_missing"' in json_text


def test_orphans_exclude_globs(tmp_path):
    _write_graph(tmp_path, code_refs=[])
    _write(tmp_path / "src/generated/model.py", "def generated_symbol():\n    pass\n")
    _write(tmp_path / "src/model.py", "def real_symbol():\n    pass\n")

    report = find_orphans(repo_root=tmp_path, excludes=["src/generated/*"])

    assert [symbol.symbol for symbol in report.orphans] == ["real_symbol"]


def _write_graph(tmp_path: Path, code_refs: list[str]) -> None:
    code_ref_lines = []
    for ref in code_refs:
        path, symbol = ref.split("::")
        code_ref_lines.append(f"      - path: {path}\n        symbol: {symbol}")
    code_block = "\n".join(code_ref_lines) if code_ref_lines else "      []"
    graph = f"""project:
  id: test
  title: Test
  tex_root: paper/main.tex
  code_roots:
    - src
    - tests

nodes:
  - id: var.x
    kind: variable
    title: x
    statement: "x in R."
    code:
{code_block}

edges: []
"""
    _write(tmp_path / "mathgraph/graph.yaml", graph)
    _write(tmp_path / "paper/main.tex", "\\section{Test}\n")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
