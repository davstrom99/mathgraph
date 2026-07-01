import json
from pathlib import Path

from mathgraph_tool.render import _code_payload, _graph_payload, _render_tex_document, _tex_to_html, render_static_site
from mathgraph_tool.schema import CodeRef, GraphSpec


def test_render_static_site_writes_graph_viewer(tmp_path):
    stale = tmp_path / "refs/tests/test_stale.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("def test_stale(): pass\n", encoding="utf-8")
    generated = render_static_site(output_dir=tmp_path, compile_tex=False)

    generated_names = {path.name for path in generated}
    assert {"index.html", "graph.json", "style.css", "app.js", "render-report.json", "elk.bundled.js"} <= generated_names

    graph = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
    node = next(item for item in graph["nodes"] if item["id"] == "estimator.beta_map")

    assert node["kind"] == "estimator"
    assert node["titleImage"].startswith("math/nodes/")
    assert (tmp_path / node["titleImage"]).exists()
    assert node["layout"]["titleWidth"] > 0
    assert node["layout"]["titleHeight"] > 0
    assert node["layout"]["boxWidth"] >= node["layout"]["titleWidth"]
    assert node["layout"]["boxHeight"] >= node["layout"]["titleHeight"]
    assert node["cluster"] is None
    assert "MAP" in node["displayLabel"]
    assert node["tex"]["href"] == "tex/mathgraph/paper/declarations/estimator_beta_map.html#estimator:beta-map"
    assert "sourceHref" not in node["tex"]
    assert (tmp_path / "refs/mathgraph/paper/declarations/estimator_beta_map.tex").exists()
    assert (tmp_path / "tex/mathgraph/paper/declarations/estimator_beta_map.html").exists()
    assert "<code>prior.gaussian_beta</code>" in (
        tmp_path / "tex/mathgraph/paper/declarations/prior_gaussian_beta.html"
    ).read_text(encoding="utf-8")
    assert (tmp_path / "refs/src/linear_bayes/estimators.py.source.txt").exists()
    assert (tmp_path / "code/src/linear_bayes/estimators.py.html").exists()
    assert (tmp_path / "refs/tests/test_linear_gaussian_recovery.py.source.txt").exists()
    assert not list((tmp_path / "refs").rglob("test*.py"))
    assert not stale.exists()
    assert any(ref["label"] == "src/linear_bayes/estimators.py::beta_map_closed_form" for ref in node["code"])
    assert all(ref["vscodeHref"].startswith("vscode://file/") for ref in node["code"])
    assert all(ref["href"].startswith("code/") for ref in node["code"])
    assert all(ref["lineStart"] is not None for ref in node["code"])
    assert any(
        ref["label"] == "tests/test_linear_gaussian_recovery.py::test_closed_form_map_equals_posterior_mean"
        for ref in node["tests"]
    )
    assert any(edge["tex"]["label"] == "deriv:map-from-posterior" for edge in node["incoming"])

    edge = next(item for item in graph["edges"] if item["tex"]["label"] == "deriv:map-from-posterior")
    assert edge["tex"]["href"] == "tex/mathgraph/paper/derivations/map_from_posterior.html#deriv:map-from-posterior"

    app_js = (tmp_path / "app.js").read_text(encoding="utf-8")
    assert "graph-view" in app_js
    assert "renderGraphEdge" in app_js
    assert "new ELK()" in app_js
    assert "layoutGroup(" in app_js
    assert "buildSccGroups" in app_js
    assert "nodeBox(" in app_js
    assert "KIND_COLORS" in app_js
    assert 'addEventListener("wheel"' in app_js
    assert "screenToGraphPoint" in app_js
    assert "zoom-in" not in app_js
    assert "Raw mirror" not in app_js
    assert "tex.sourceHref" not in app_js
    assert "applyGraphTransform" in app_js
    assert "scheduleGraphTransform" in app_js
    assert 'id="graph-viewport"' in app_js
    assert "updateGraphSelection" in app_js
    assert app_js.count("renderGraph();") == 1
    assert "typesetMath" not in app_js
    assert "foreignObject" not in app_js
    assert "node-title-image" in app_js
    assert "dependencyLayers" not in app_js
    assert "edgeTrack" not in app_js

    index_html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "tex-svg.js" not in index_html
    assert 'vendor/elk.bundled.js?v=elk-layout-1' in index_html
    assert (tmp_path / "vendor" / "elk.bundled.js").exists()

    report = json.loads((tmp_path / "render-report.json").read_text(encoding="utf-8"))
    assert all(item["status"] == "rendered" for item in report["node_titles"])
    assert all(item["titleWidth"] > 0 for item in report["node_titles"])
    assert all(item["titleHeight"] > 0 for item in report["node_titles"])


def test_tex_converter_renders_align_starred_sections_and_paragraphs():
    source = r"""\section*{Mathematical objects}
\begin{align}
\boldsymbol{\alpha}&=(b_1,c_1,\ldots,b_M,c_M)\in(-1,1)^M\times(-1,0)^M\\
\mathbf{s}[n]&\in\mathbb{R}^{2M}\\
p(\mathbf{s}[n]&\mid r[0{:}n])
\end{align}
\par Office audio dataset.
\par Numerical and end-to-end validation suite.
"""

    rendered = _tex_to_html(source)

    assert "<h2>Mathematical objects</h2>" in rendered
    assert r"\[\begin{aligned}" in rendered
    assert r"\boldsymbol{\alpha}" in rendered
    assert r"\end{aligned}\]" in rendered
    assert "<p>Office audio dataset.</p>" in rendered
    assert "<p>Numerical and end-to-end validation suite.</p>" in rendered
    assert r"\section*" not in rendered
    assert r"\begin{align}" not in rendered


def test_compiled_derivation_page_embeds_local_pdf():
    rendered = _render_tex_document(
        "derivation.tex",
        "../../../style.css",
        r"\[x = 1\]",
        pdf_name="derivation.pdf",
    )

    assert 'class="derivation-frame"' in rendered
    assert 'src="derivation.pdf#view=FitH"' in rendered
    assert "tex-svg.js" not in rendered


def test_exact_line_code_reference_links_to_source_line(tmp_path):
    source = tmp_path / "model.py"
    source.write_text("x = 1\ny = x + 1\n", encoding="utf-8")

    payload = _code_payload(CodeRef(path="model.py", line=2), Path(tmp_path))

    assert payload["label"] == "model.py:2"
    assert payload["href"] == "code/model.py.html#L2"
    assert payload["lineStart"] == 2
    assert payload["lineEnd"] == 2


def test_graph_payload_marks_nontrivial_scc_membership(tmp_path):
    graph = GraphSpec.model_validate(
        {
            "project": {"id": "cycle", "title": "Cycle", "tex_root": "mathgraph/paper/main.tex"},
            "nodes": [
                {
                    "id": "var.a",
                    "kind": "variable",
                    "title": "A",
                    "statement": "Variable A.",
                },
                {
                    "id": "assumption.b",
                    "kind": "assumption",
                    "title": "B",
                    "statement": "Depends on A.",
                    "uses": ["var.a"],
                },
                {
                    "id": "assumption.c",
                    "kind": "assumption",
                    "title": "C",
                    "statement": "Depends on A.",
                    "uses": ["var.a"],
                },
            ],
            "edges": [
                {
                    "from": "assumption.b",
                    "to": "assumption.c",
                    "kind": "depends_on",
                    "description": "B depends on C.",
                    "tex": {"file": "mathgraph/paper/derivations/init_index_products.tex", "label": "cycle:b-c"},
                },
                {
                    "from": "assumption.c",
                    "to": "assumption.b",
                    "kind": "depends_on",
                    "description": "C depends on B.",
                    "tex": {"file": "mathgraph/paper/derivations/init_index_products.tex", "label": "cycle:c-b"},
                },
            ],
        }
    )

    payload = _graph_payload(graph, Path(tmp_path))
    clusters = payload["clusters"]
    assert len(clusters) == 1
    assert clusters[0]["size"] == 2
    node_clusters = {node["id"]: node["cluster"] for node in payload["nodes"]}
    assert node_clusters["var.a"] is None
    assert node_clusters["assumption.b"]["id"] == clusters[0]["id"]
    assert node_clusters["assumption.c"]["id"] == clusters[0]["id"]


def test_graph_payload_serializes_fallback_box_metadata(tmp_path):
    graph = GraphSpec.model_validate(
        {
            "project": {"id": "fallback", "title": "Fallback", "tex_root": "mathgraph/paper/main.tex"},
            "nodes": [
                {
                    "id": "var.f",
                    "kind": "variable",
                    "title": "Fallback",
                    "statement": "Fallback title node.",
                }
            ],
            "edges": [],
        }
    )

    payload = _graph_payload(
        graph,
        Path(tmp_path),
        {
            "var.f": {
                "path": None,
                "titleWidth": 132.0,
                "titleHeight": 24.0,
                "boxWidth": 196.0,
                "boxHeight": 82.0,
            }
        },
    )

    node = payload["nodes"][0]
    assert node["titleImage"] is None
    assert node["layout"] == {
        "titleWidth": 132.0,
        "titleHeight": 24.0,
        "boxWidth": 196.0,
        "boxHeight": 82.0,
    }
