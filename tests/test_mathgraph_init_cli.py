from mathgraph_tool.cli import main


def test_init_cli_dry_run_reports_planned_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "--dry-run", "--project-id", "demo", "--title", "Demo"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Would create mathgraph scaffold" in output
    assert "mathgraph/graph.yaml" in output
    assert "mathgraph/INIT_REPORT.md" in output
    assert "mathgraph/INIT_INDEX.jsonl" in output
    assert "mathgraph/paper/main.tex" in output
    assert "full onboarding workflow" in output
    assert not (tmp_path / "mathgraph/graph.yaml").exists()


def test_index_cli_build_summary_show_find_and_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "model.py").write_text("beta = 1\n", encoding="utf-8")

    assert main(["index", "build"]) == 0
    assert main(["index", "summary"]) == 0
    assert main(["index", "show", "model.py"]) == 0
    assert main(["index", "find", "beta"]) == 0
    assert main(["index", "dossier"]) == 0
    assert main(["draft-refs", "beta"]) == 0
    assert main(["index", "check"]) == 0

    output = capsys.readouterr().out
    assert "Indexed 1 semantic files and 0 aggregate families" in output
    assert "model.py [python/ok]" in output
    assert "File: model.py" in output
    assert "model.py:1: beta = 1" in output
    assert "Evidence entries:" in output
    assert "role: definition" in output
    assert "index covers 1 semantic files and 0 aggregate families" in output


def test_orphans_cli_returns_nonzero_for_unattached_symbol(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mathgraph").mkdir()
    (tmp_path / "paper").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "paper/main.tex").write_text("\\section{Test}\n", encoding="utf-8")
    (tmp_path / "src/model.py").write_text("def missing():\n    pass\n", encoding="utf-8")
    (tmp_path / "mathgraph/graph.yaml").write_text(
        """
project:
  id: demo
  title: Demo
  tex_root: paper/main.tex
  code_roots:
    - src

nodes: []
edges: []
""",
        encoding="utf-8",
    )

    exit_code = main(["orphans"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "src/model.py::missing" in output


def test_init_review_mode_flags_are_mutually_exclusive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    try:
        main(["init", "--include-generated", "--full-review"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("argparse should reject conflicting review modes")
