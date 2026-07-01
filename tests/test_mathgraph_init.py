from pathlib import Path

from mathgraph_tool.checks import format_check_result, run_checks
from mathgraph_tool.init import initialize_mathgraph


def test_init_empty_project_creates_valid_empty_graph(tmp_path):
    result = initialize_mathgraph(tmp_path, project_id="empty_project", title="Empty Project")

    assert result.ok
    assert result.checklist_count == 0
    assert (tmp_path / "mathgraph/graph.yaml").exists()
    assert (tmp_path / "mathgraph/INIT_CHECKLIST.md").exists()
    assert (tmp_path / "mathgraph/INIT_REPORT.md").exists()
    assert (tmp_path / "mathgraph/INIT_INDEX.jsonl").exists()
    assert (tmp_path / "mathgraph/paper/main.tex").exists()
    assert not (tmp_path / "mathgraph/paper/derivations.tex").exists()
    assert not (tmp_path / "paper").exists()
    assert "No eligible project files were found" in (tmp_path / "mathgraph/INIT_CHECKLIST.md").read_text(encoding="utf-8")
    report = (tmp_path / "mathgraph/INIT_REPORT.md").read_text(encoding="utf-8")
    assert "filled by Codex during `/mathgraph init`" in report
    assert "Initial Graph Summary" in report
    assert "Line-level use-site coverage" in report
    assert "Review mode: `source`" in report
    assert (tmp_path / "mathgraph/INIT_DRAFT.yaml").exists()

    check = run_checks(repo_root=tmp_path)
    assert check.passed, format_check_result(check)
    assert check.graph is not None
    assert check.graph.nodes == []
    assert check.graph.edges == []


def test_init_existing_project_checklist_includes_eligible_files_and_excludes_generated(tmp_path):
    _write(tmp_path / "src/model.py", "def fit():\n    pass\n")
    _write(tmp_path / "analysis.jl", "f(x) = x\n")
    _write(tmp_path / "paper.tex", "\\section{Model}\n")
    _write(tmp_path / "notes.md", "# Notes\n")
    _write(tmp_path / "paper.pdf", "%PDF-1.4\n")
    _write(tmp_path / "paper.aux", "generated")
    _write(tmp_path / "figure.png", "not included")
    _write(tmp_path / ".venv/lib/site.py", "def ignored():\n    pass\n")
    _write(tmp_path / "web/app.js", "console.log('generated')\n")

    result = initialize_mathgraph(tmp_path)

    checklist = (tmp_path / "mathgraph/INIT_CHECKLIST.md").read_text(encoding="utf-8")
    assert result.checklist_count == 6
    assert "Codex instruction for `/mathgraph init`" in checklist
    assert "mathgraph/INIT_REPORT.md" in checklist
    assert "path` plus `line`" in checklist
    assert "each distinct derivation in its own standalone TeX file" in checklist
    assert "mathgraph index show <path>" in checklist
    assert "`src/model.py`" in checklist
    assert "`analysis.jl`" in checklist
    assert "`paper.tex`" in checklist
    assert "`notes.md`" in checklist
    assert "binary artifacts" in checklist
    assert "`web`" in checklist
    assert "paper.aux" not in checklist
    assert "figure.png" not in checklist
    assert ".venv" not in checklist
    assert "web/app.js" not in checklist
    report = (tmp_path / "mathgraph/INIT_REPORT.md").read_text(encoding="utf-8")
    assert "Review mode: `source`" in report
    assert "`web`: 1 files, hashes verified (rendered)" in report
    assert "`binary artifacts`: 2 files, hashes verified (binary)" in report


def test_init_refuses_existing_scaffold_by_default(tmp_path):
    _write(tmp_path / "mathgraph/graph.yaml", "project: {}\n")

    result = initialize_mathgraph(tmp_path)

    assert not result.ok
    assert result.existing == [tmp_path / "mathgraph/graph.yaml"]


def test_init_appends_to_existing_agents_file(tmp_path):
    _write(tmp_path / "AGENTS.md", "# Existing Rules\n\nKeep this line.\n")

    result = initialize_mathgraph(tmp_path)

    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert result.ok
    assert "# Existing Rules" in agents
    assert "Keep this line." in agents
    assert "Mathgraph-Centered Repository Rules" in agents
    assert agents.count("mathgraph-rules:start") == 1
    assert "every source line" in agents
    assert "every distinct derivation in its own standalone-compilable TeX file" in agents
    assert "Multiple edges may share" in agents
    assert "render-report.json" in agents


def test_init_does_not_duplicate_existing_agents_mathgraph_section(tmp_path):
    result = initialize_mathgraph(tmp_path)
    second_result = initialize_mathgraph(tmp_path, force=True)

    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert result.ok
    assert second_result.ok
    assert agents.count("mathgraph-rules:start") == 1


def test_init_existing_agents_file_does_not_refuse(tmp_path):
    _write(tmp_path / "AGENTS.md", "# Existing Rules\n")

    result = initialize_mathgraph(tmp_path)

    assert result.ok


def test_init_dry_run_does_not_write(tmp_path):
    _write(tmp_path / "src/model.py", "def fit():\n    pass\n")

    result = initialize_mathgraph(tmp_path, dry_run=True)

    assert result.ok
    assert result.dry_run
    assert result.checklist_count == 1
    assert not (tmp_path / "mathgraph/graph.yaml").exists()


def test_init_dry_run_refuses_existing_scaffold_without_force(tmp_path):
    _write(tmp_path / "mathgraph/graph.yaml", "project: {}\n")

    result = initialize_mathgraph(tmp_path, dry_run=True)

    assert not result.ok
    assert result.refused


def test_init_force_overwrites_scaffold(tmp_path):
    _write(tmp_path / "mathgraph/graph.yaml", "old")

    result = initialize_mathgraph(tmp_path, force=True, project_id="forced", title="Forced")

    assert result.ok
    assert "id: forced" in (tmp_path / "mathgraph/graph.yaml").read_text(encoding="utf-8")


def test_init_full_review_records_explicit_mode_and_allows_unsupported_files(tmp_path):
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4\n")

    result = initialize_mathgraph(tmp_path, full_review=True)

    assert result.ok
    assert result.review_mode == "full"
    checklist = (tmp_path / "mathgraph/INIT_CHECKLIST.md").read_text(encoding="utf-8")
    assert "Review mode: `full`" in checklist
    assert "Read every eligible file completely" in checklist
    check = run_checks(repo_root=tmp_path)
    assert check.passed, format_check_result(check)
    assert any("requires complete semantic review" in warning for warning in check.warnings)


def test_init_source_mode_aggregates_unsupported_binary_files(tmp_path):
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4\n")

    result = initialize_mathgraph(tmp_path)

    assert result.ok
    assert result.blocked_count == 0
    checklist = (tmp_path / "mathgraph/INIT_CHECKLIST.md").read_text(encoding="utf-8")
    assert "binary artifacts" in checklist
    assert (tmp_path / "mathgraph/INIT_INDEX.jsonl").exists()


def test_init_groups_generated_family_and_supports_explicit_include_generated(tmp_path):
    _write(tmp_path / "src/model.py", "x = 1\n")
    for index in range(12):
        _write(tmp_path / f"graphify-out/cache/{index}.json", '{"x": 1}\n')

    source = initialize_mathgraph(tmp_path)
    checklist = (tmp_path / "mathgraph/INIT_CHECKLIST.md").read_text(encoding="utf-8")

    assert source.review_mode == "source"
    assert source.checklist_count == 2
    assert "graphify-out/cache` - cache; 12 files" in checklist
    assert "graphify-out/cache/0.json" not in checklist

    included = initialize_mathgraph(tmp_path, force=True, include_generated=True)
    included_checklist = (tmp_path / "mathgraph/INIT_CHECKLIST.md").read_text(encoding="utf-8")
    assert included.review_mode == "include-generated"
    assert "graphify-out/cache/0.json" in included_checklist


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
