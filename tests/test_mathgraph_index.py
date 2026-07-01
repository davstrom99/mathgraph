from pathlib import Path

from mathgraph_tool.checks import format_check_result, run_checks
from mathgraph_tool.discovery import discover_project_files
from mathgraph_tool.indexing import (
    build_index,
    check_index,
    format_index_file,
    format_index_dossier,
    format_index_find,
    format_index_summary,
    draft_code_refs,
    load_index,
)


def test_indexes_python_matlab_and_tex_evidence(tmp_path):
    _write(
        tmp_path / "model.py",
        '''import numpy as np

def estimate(x: float = 1.0):
    """Posterior MAP estimate under a Gaussian model."""
    assert x > 0
    sample = np.random.normal(0, x)
    output = "results/estimate.json"
    return sample, output
''',
    )
    _write(
        tmp_path / "fit.m",
        """%% Gaussian estimator
function [mu] = fit_model(X, y)
assert(size(X, 1) == numel(y));
noise = randn(size(y));
mu = (X' * X) \\ (X' * (y + noise));
save('results/fit.mat', 'mu');
end
""",
    )
    _write(
        tmp_path / "model.tex",
        r"""\section{Model}
\newcommand{\betaMAP}{\hat\beta}
The posterior estimator is
\begin{equation}
\betaMAP = (X^T X)^{-1}X^T y.
\label{eq:map}
\end{equation}
""",
    )

    result = build_index(tmp_path)
    _, records = load_index(tmp_path)
    by_path = {record["path"]: record for record in records}

    assert result.passed
    assert by_path["model.py"]["parser"] == "python-ast-tokenize-v1"
    assert by_path["model.py"]["identifiers"]["sample"] == [6, 8]
    assert by_path["model.py"]["assertions"] == [5]
    assert by_path["model.py"]["defaults"][0]["name"] == "x"
    assert by_path["model.py"]["outputs"] == [{"line": 7, "path": "results/estimate.json"}]
    assert by_path["fit.m"]["symbols"][0]["name"] == "fit_model"
    assert by_path["fit.m"]["assertions"] == [3]
    assert any(region["kind"] == "mathematical-call" for region in by_path["fit.m"]["regions"])
    assert any(item["name"] == "eq:map" for item in by_path["model.tex"]["symbols"])
    assert any(region["kind"] == "equation" and region["start_line"] == 4 for region in by_path["model.tex"]["regions"])


def test_index_reuses_unchanged_records_and_detects_stale_files(tmp_path):
    _write(tmp_path / "model.py", "x = 1\n")

    first = build_index(tmp_path)
    second = build_index(tmp_path)
    _write(tmp_path / "model.py", "x = 2\n")
    stale = check_index(tmp_path)
    refreshed = build_index(tmp_path)

    assert first.reused == 0
    assert second.reused == 1
    assert not stale.passed
    assert "indexed file is stale: model.py" in stale.errors
    assert refreshed.reused == 0
    assert check_index(tmp_path).passed


def test_index_check_preserves_custom_discovery_scope(tmp_path):
    _write(tmp_path / "model.py", "x = 1\n")
    _write(tmp_path / "notes.md", "# Model notes\n")

    build_index(tmp_path, include_extensions={".py"})

    assert check_index(tmp_path).passed
    _, records = load_index(tmp_path)
    assert [record["path"] for record in records] == ["model.py"]


def test_malformed_json_is_blocked(tmp_path):
    _write(tmp_path / "config.json", "{not-json}\n")

    result = build_index(tmp_path)

    assert not result.passed
    assert result.records[0]["status"] == "blocked"


def test_python_utf8_bom_is_supported_without_shifting_lines(tmp_path):
    (tmp_path / "model.py").write_bytes(b"\xef\xbb\xbfx = 1\n")

    result = build_index(tmp_path)

    assert result.passed
    assert result.records[0]["identifiers"]["x"] == [1]


def test_unsupported_and_malformed_files_block_only_indexed_mode(tmp_path):
    _write(tmp_path / "broken.py", "def broken(:\n")
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4\n")

    indexed = build_index(tmp_path)
    indexed_check = check_index(tmp_path)
    full = build_index(tmp_path, full_review=True)
    full_check = check_index(tmp_path)

    assert indexed.blocked == 1
    assert not indexed.passed
    assert not indexed_check.passed
    assert full.passed
    assert full_check.passed
    assert len(full_check.warnings) == 2


def test_index_queries_are_bounded_and_include_exact_source_lines(tmp_path):
    _write(tmp_path / "model.py", "beta = 1\nposterior = beta + 2\n")
    build_index(tmp_path)

    summary = format_index_summary(tmp_path, limit=1)
    shown = format_index_file(tmp_path, "model.py", limit=1)
    found = format_index_find(tmp_path, "beta", limit=1)
    found_second = format_index_find(tmp_path, "beta", limit=1, offset=1)

    assert "model.py [python/ok]" in summary
    assert shown.count("- assignment") == 1
    assert "... 1 more regions; rerun with `--offset 1`" in shown
    assert "Occurrences: 2" in found
    assert "model.py:1: beta = 1" in found
    assert "... 1 more occurrences; rerun with `--offset 1`" in found
    assert "model.py:2: posterior = beta + 2" in found_second


def test_indexed_regions_reduce_mixed_fixture_input_by_half(tmp_path):
    python_boilerplate = "\n".join("# ordinary implementation detail" for _ in range(120))
    _write(
        tmp_path / "model.py",
        f"{python_boilerplate}\n\ndef posterior(beta=1.0):\n    assert beta > 0\n    return beta\n",
    )
    matlab_boilerplate = "\n".join("% ordinary implementation detail" for _ in range(80))
    _write(
        tmp_path / "fit.m",
        f"{matlab_boilerplate}\n%% MAP estimator\nfunction b = fit_map(X, y)\nb = X \\ y;\nend\n",
    )
    _write(
        tmp_path / "model.tex",
        "Prose.\n" * 50 + "\\begin{equation}\n\\hat\\beta = X^T y\n\\end{equation}\n",
    )

    result = build_index(tmp_path)
    raw_characters = sum((tmp_path / item.path).stat().st_size for item in discover_project_files(tmp_path))
    reviewed_characters = 0
    for record in result.records:
        lines = (tmp_path / record["path"]).read_text(encoding="utf-8").splitlines()
        reviewed_lines = {
            line
            for region in record["regions"]
            for line in range(region["start_line"], region["end_line"] + 1)
        }
        reviewed_characters += sum(len(lines[line - 1]) + 1 for line in reviewed_lines)

    assert result.passed
    assert reviewed_characters <= raw_characters * 0.5
    assert "posterior" in result.records[1]["identifiers"] or any(
        "posterior" in record["identifiers"] for record in result.records
    )


def test_mathgraph_check_rejects_exact_line_reference_outside_index(tmp_path):
    _write(tmp_path / "model.py", "x = 1\n")
    _write(tmp_path / "paper/main.tex", "\\label{def:x}\n")
    build_index(tmp_path)
    _write(tmp_path / "mathgraph/helper.py", "x = 1\n")
    _write(
        tmp_path / "mathgraph/graph.yaml",
        """
project:
  id: demo
  title: Demo
  tex_root: paper/main.tex
nodes:
  - id: var.x
    kind: variable
    title: "x in R"
    symbol: x
    statement: "x in R."
    tex: {file: paper/main.tex, label: def:x}
    code:
      - {path: mathgraph/helper.py, line: 1}
edges: []
""",
    )

    result = run_checks(repo_root=tmp_path)

    assert not result.passed
    assert "code reference is outside indexed evidence" in format_check_result(result)


def test_generated_cache_family_is_aggregated_and_dossier_is_compact(tmp_path):
    for index in range(10):
        _write(tmp_path / f"src/model_{index}.py", f"def estimate_{index}(x):\n    return x + {index}\n")
    for index in range(76):
        _write(tmp_path / f"graphify-out/cache/item_{index}.json", '{"cached": true}\n')

    result = build_index(tmp_path)
    families = [record for record in result.records if record["record_type"] == "family"]
    summary = format_index_summary(tmp_path)
    dossier = format_index_dossier(tmp_path)

    assert len(families) == 1
    assert families[0]["family"] == "graphify-out/cache"
    assert families[0]["file_count"] == 76
    assert "item_0.json" not in summary
    assert "graphify-out/cache: 76 files, hashes verified" in dossier

    expanded = build_index(tmp_path, include_generated=True)
    expanded_text = "\n".join(
        format_index_file(tmp_path, record["path"])
        for record in expanded.records
        if record["record_type"] == "file"
    )
    assert len(dossier) < len(expanded_text) * 0.5


def test_project_config_can_reclassify_generated_source(tmp_path):
    _write(
        tmp_path / "pyproject.toml",
        '[tool.mathgraph.init]\nauthoritative = ["graphify-out/cache/keep.json"]\n',
    )
    _write(tmp_path / "graphify-out/cache/keep.json", '{"model": 1}\n')
    _write(tmp_path / "graphify-out/cache/drop.json", '{"cache": 1}\n')

    result = build_index(tmp_path)

    files = [record for record in result.records if record["record_type"] == "file"]
    families = [record for record in result.records if record["record_type"] == "family"]
    assert any(record["path"] == "graphify-out/cache/keep.json" for record in files)
    assert families[0]["file_count"] == 1


def test_draft_refs_classifies_definition_call_test_experiment_and_configuration(tmp_path):
    _write(tmp_path / "src/model.py", "def estimate(x):\n    return x\n\ndef run():\n    return estimate(1)\n")
    _write(tmp_path / "tests/test_model.py", "from model import estimate\ndef test_estimate():\n    assert estimate(1) == 1\n")
    _write(tmp_path / "experiments/run.py", "from model import estimate\nvalue = estimate(2)\n")
    build_index(tmp_path)

    draft = draft_code_refs(tmp_path, "estimate")
    roles = {item["role"] for item in draft["code"]}

    assert {"definition", "caller", "test", "experiment"} <= roles
    assert all(item["line"] >= 1 for item in draft["code"])
    assert all("path" in item for item in draft["code"])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
