"""Static webpage renderer for mathgraph."""

from __future__ import annotations

import json
import os
import ast
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

import networkx as nx
from mathgraph_tool.discovery import CODE_EXTENSIONS

from mathgraph_tool.loader import find_repo_root, load_graph
from mathgraph_tool.schema import CodeRef, Edge, GraphSpec, Node, OutputRef, TexRef


DEFAULT_WEB_DIR = Path("web")
TEX_RENDER_VERSION = 1
ASSET_VERSION = "elk-layout-1"
NODE_BOX_MIN_WIDTH = 190.0
NODE_BOX_MIN_HEIGHT = 82.0
NODE_BOX_HORIZONTAL_PADDING = 52.0
NODE_BOX_VERTICAL_PADDING = 40.0
STATIC_ASSET_SOURCES = {
    Path("vendor/elk.bundled.js"): Path(__file__).resolve().parent / "static" / "vendor" / "elk.bundled.js",
}


def render_static_site(
    output_dir: str | Path = DEFAULT_WEB_DIR,
    graph: GraphSpec | None = None,
    *,
    compile_tex: bool = True,
) -> list[Path]:
    """Render the graph viewer and return generated paths."""
    repo_root = find_repo_root()
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path.mkdir(parents=True, exist_ok=True)

    graph = graph or load_graph(repo_root=repo_root)
    _copy_referenced_files(graph, repo_root, output_path)
    title_images, title_report = _render_node_title_images(graph, output_path)
    tex_report = _render_tex_files(graph, repo_root, output_path, compile_tex=compile_tex)
    _render_code_files(graph, repo_root, output_path)
    static_assets = _copy_static_assets(output_path)
    files: dict[Path, str] = {
        output_path / "graph.json": json.dumps(_graph_payload(graph, repo_root, title_images), indent=2),
        output_path / "index.html": _index_html(),
        output_path / "style.css": _style_css(),
        output_path / "app.js": _app_js(),
        output_path / "render-report.json": json.dumps(
            {"node_titles": title_report, "tex": tex_report}, indent=2
        ),
    }
    for path, text in files.items():
        path.write_text(text, encoding="utf-8")
    return list(files) + static_assets


def _copy_referenced_files(graph: GraphSpec, repo_root: Path, output_path: Path) -> None:
    refs_root = output_path / "refs"
    if refs_root.exists():
        shutil.rmtree(refs_root)
    for relative_path in _referenced_paths(graph):
        source = repo_root / relative_path
        if not source.exists() or not source.is_file():
            continue
        destination_relative = relative_path
        if relative_path.suffix in CODE_EXTENSIONS:
            destination_relative = relative_path.with_suffix(relative_path.suffix + ".source.txt")
        destination = refs_root / destination_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _render_tex_files(
    graph: GraphSpec,
    repo_root: Path,
    output_path: Path,
    *,
    compile_tex: bool,
) -> list[dict]:
    tex_paths = {Path(ref.file) for _, ref in graph.all_tex_refs()}
    derivation_paths = {Path(edge.tex.file) for edge in graph.edges}
    if graph.project.tex_root:
        tex_paths.add(Path(graph.project.tex_root))

    compile_results: dict[Path, dict] = {}
    if compile_tex and shutil.which("pdflatex"):
        jobs = []
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(derivation_paths)))) as executor:
            for relative_path in sorted(derivation_paths):
                source = repo_root / relative_path
                rendered_pdf = output_path / _tex_render_path(relative_path).with_suffix(".pdf")
                if source.exists() and source.is_file():
                    jobs.append((relative_path, executor.submit(_compile_tex_pdf, source, rendered_pdf, repo_root)))
            for relative_path, future in jobs:
                compile_results[relative_path] = future.result()

    report: list[dict] = []
    for relative_path in sorted(tex_paths):
        source = repo_root / relative_path
        if not source.exists() or not source.is_file():
            continue
        rendered = output_path / _tex_render_path(relative_path)
        rendered.parent.mkdir(parents=True, exist_ok=True)
        style_href = Path(os.path.relpath(output_path / "style.css", rendered.parent)).as_posix()
        compilation = compile_results.get(relative_path)
        pdf_name = rendered.with_suffix(".pdf").name if compilation and compilation["status"] in {"compiled", "cached"} else None
        rendered.write_text(
            _render_tex_document(
                relative_path.as_posix(),
                style_href,
                source.read_text(encoding="utf-8-sig"),
                pdf_name=pdf_name,
                render_error=compilation.get("error") if compilation else None,
            ),
            encoding="utf-8",
        )
        report.append(
            {
                "file": relative_path.as_posix(),
                "kind": "derivation" if relative_path in derivation_paths else "document",
                "status": compilation["status"] if compilation else "browser-rendered",
                "error": compilation.get("error") if compilation else None,
            }
        )
    return report


def _render_node_title_images(graph: GraphSpec, output_path: Path) -> tuple[dict[str, dict], list[dict]]:
    from matplotlib.backends.backend_svg import FigureCanvasSVG
    from matplotlib.figure import Figure

    image_dir = output_path / "math" / "nodes"
    image_dir.mkdir(parents=True, exist_ok=True)
    images: dict[str, dict] = {}
    report: list[dict] = []
    for node in graph.nodes:
        label = node.display_label or node.title
        filename = re.sub(r"[^A-Za-z0-9_.-]+", "_", node.id) + ".svg"
        destination = image_dir / filename
        expression = _mathtext_label(label)
        try:
            figure = Figure(figsize=(3.2, 0.55), dpi=120)
            FigureCanvasSVG(figure)
            figure.patch.set_alpha(0)
            figure.text(0.01, 0.5, expression, fontsize=14, va="center", color="#18212b")
            figure.savefig(destination, format="svg", transparent=True, bbox_inches="tight", pad_inches=0.02)
            title_width, title_height = _parse_svg_dimensions(destination)
            box_width, box_height = _node_box_dimensions(title_width, title_height)
            images[node.id] = {
                "path": (Path("math") / "nodes" / filename).as_posix(),
                "titleWidth": title_width,
                "titleHeight": title_height,
                "boxWidth": box_width,
                "boxHeight": box_height,
            }
            report.append(
                {
                    "node": node.id,
                    "status": "rendered",
                    "error": None,
                    "titleWidth": title_width,
                    "titleHeight": title_height,
                }
            )
        except Exception as exc:
            title_width, title_height = _fallback_title_dimensions(label)
            box_width, box_height = _node_box_dimensions(title_width, title_height)
            images[node.id] = {
                "path": None,
                "titleWidth": title_width,
                "titleHeight": title_height,
                "boxWidth": box_width,
                "boxHeight": box_height,
            }
            report.append(
                {
                    "node": node.id,
                    "status": "text-fallback",
                    "error": str(exc),
                    "titleWidth": title_width,
                    "titleHeight": title_height,
                }
            )
    return images, report


def _copy_static_assets(output_path: Path) -> list[Path]:
    written: list[Path] = []
    for relative_path, source in STATIC_ASSET_SOURCES.items():
        if not source.exists():
            continue
        destination = output_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        written.append(destination)
    return written


def _parse_svg_dimensions(path: Path) -> tuple[float, float]:
    root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
    width = _parse_svg_length(root.get("width"))
    height = _parse_svg_length(root.get("height"))
    if width is not None and height is not None:
        return width, height
    view_box = root.get("viewBox", "").strip().split()
    if len(view_box) == 4:
        return float(view_box[2]), float(view_box[3])
    raise ValueError(f"could not determine SVG dimensions for {path}")


def _parse_svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    return float(match.group(1))


def _fallback_title_dimensions(label: str) -> tuple[float, float]:
    plain = re.sub(r"\\[()[\]]", "", label).strip()
    width = max(96.0, min(420.0, 24.0 + len(plain) * 7.4))
    return width, 24.0


def _node_box_dimensions(title_width: float, title_height: float) -> tuple[float, float]:
    return (
        max(NODE_BOX_MIN_WIDTH, round(title_width + NODE_BOX_HORIZONTAL_PADDING, 2)),
        max(NODE_BOX_MIN_HEIGHT, round(title_height + NODE_BOX_VERTICAL_PADDING, 2)),
    )


def _mathtext_label(label: str) -> str:
    value = label.strip()
    if value.startswith(r"\(") and value.endswith(r"\)"):
        return f"${value[2:-2]}$"
    if value.startswith(r"\[") and value.endswith(r"\]"):
        return f"${value[2:-2]}$"
    return value


def _compile_tex_pdf(source: Path, destination: Path, repo_root: Path) -> dict:
    metadata = destination.with_suffix(".pdf.meta.json")
    signature = {
        "version": TEX_RENDER_VERSION,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "source_size": source.stat().st_size,
    }
    if destination.exists() and metadata.exists():
        try:
            if json.loads(metadata.read_text(encoding="utf-8")) == signature:
                return {"status": "cached", "error": None}
        except (json.JSONDecodeError, OSError):
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding="utf-8-sig")
    if r"\documentclass" not in content:
        content = (
            "\\documentclass{article}\n"
            "\\usepackage{amsmath,amssymb,bm,mathtools}\n"
            "\\usepackage[margin=0.65in]{geometry}\n"
            "\\pagestyle{empty}\n"
            "\\begin{document}\n"
            f"{content}\n"
            "\\end{document}\n"
        )
    try:
        with tempfile.TemporaryDirectory(prefix="mathgraph-tex-") as temp_name:
            temp = Path(temp_name)
            tex_path = temp / "derivation.tex"
            tex_path.write_text(content, encoding="utf-8")
            environment = os.environ.copy()
            existing_inputs = environment.get("TEXINPUTS", "")
            environment["TEXINPUTS"] = os.pathsep.join(
                [str(source.parent), str(repo_root), existing_inputs]
            )
            completed = subprocess.run(
                [
                    shutil.which("pdflatex") or "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-output-directory={temp}",
                    str(tex_path),
                ],
                cwd=source.parent,
                env=environment,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            pdf = temp / "derivation.pdf"
            if completed.returncode != 0 or not pdf.exists():
                output = (completed.stdout + "\n" + completed.stderr).strip()
                return {"status": "browser-fallback", "error": output[-1200:] or "pdflatex failed"}
            shutil.copy2(pdf, destination)
            metadata.write_text(json.dumps(signature, sort_keys=True), encoding="utf-8")
            return {"status": "compiled", "error": None}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "browser-fallback", "error": str(exc)}


def _render_code_files(graph: GraphSpec, repo_root: Path, output_path: Path) -> None:
    code_paths = {Path(ref.path) for _, ref in graph.all_code_refs()}
    for relative_path in code_paths:
        source = repo_root / relative_path
        if not source.exists() or not source.is_file():
            continue
        rendered = output_path / _code_render_path(relative_path)
        rendered.parent.mkdir(parents=True, exist_ok=True)
        style_href = Path(os.path.relpath(output_path / "style.css", rendered.parent)).as_posix()
        rendered.write_text(
            _render_code_document(relative_path.as_posix(), style_href, source.read_text(encoding="utf-8")),
            encoding="utf-8",
        )


def _referenced_paths(graph: GraphSpec) -> set[Path]:
    paths: set[Path] = set()
    if graph.project.tex_root:
        paths.add(Path(graph.project.tex_root))
    for _, ref in graph.all_tex_refs():
        paths.add(Path(ref.file))
    for _, ref in graph.all_code_refs():
        paths.add(Path(ref.path))
    for node in graph.nodes:
        for output in node.outputs:
            paths.add(Path(output.path))
    return paths


def _graph_payload(graph: GraphSpec, repo_root: Path, title_images: dict[str, dict] | None = None) -> dict:
    incoming: dict[str, list[Edge]] = {node.id: [] for node in graph.nodes}
    outgoing: dict[str, list[Edge]] = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        outgoing[edge.from_].append(edge)
        incoming[edge.to].append(edge)
    cluster_memberships, clusters = _cluster_memberships(graph)

    return {
        "project": graph.project.model_dump(mode="json"),
        "nodes": [
            _node_payload(
                node,
                incoming[node.id],
                outgoing[node.id],
                repo_root,
                (title_images or {}).get(node.id),
                cluster_memberships.get(node.id),
            )
            for node in graph.nodes
        ],
        "edges": [_edge_payload(edge, repo_root) for edge in graph.edges],
        "clusters": clusters,
    }


def _node_payload(
    node: Node,
    incoming: list[Edge],
    outgoing: list[Edge],
    repo_root: Path,
    title_asset: dict | None = None,
    cluster: dict | None = None,
) -> dict:
    title_asset = title_asset or {}
    return {
        "id": node.id,
        "kind": node.kind.value,
        "title": node.title,
        "displayLabel": node.display_label or node.title,
        "titleImage": title_asset.get("path"),
        "layout": {
            "titleWidth": title_asset.get("titleWidth"),
            "titleHeight": title_asset.get("titleHeight"),
            "boxWidth": title_asset.get("boxWidth", NODE_BOX_MIN_WIDTH),
            "boxHeight": title_asset.get("boxHeight", NODE_BOX_MIN_HEIGHT),
        },
        "cluster": cluster,
        "statement": node.statement,
        "symbol": node.symbol,
        "uses": node.uses or [],
        "tex": _tex_payload(node.tex, repo_root),
        "code": [_code_payload(ref, repo_root) for ref in node.code if not _is_test_ref(ref)],
        "tests": [_code_payload(ref, repo_root) for ref in node.code if _is_test_ref(ref)],
        "outputs": [_output_payload(ref, repo_root) for ref in node.outputs],
        "incoming": [_edge_payload(edge, repo_root) for edge in incoming],
        "outgoing": [_edge_payload(edge, repo_root) for edge in outgoing],
    }


def _cluster_memberships(graph: GraphSpec) -> tuple[dict[str, dict], list[dict]]:
    graph_nx = nx.DiGraph()
    graph_nx.add_nodes_from(node.id for node in graph.nodes)
    graph_nx.add_edges_from((edge.from_, edge.to) for edge in graph.edges)

    memberships: dict[str, dict] = {}
    clusters: list[dict] = []
    nontrivial = [
        sorted(component)
        for component in nx.strongly_connected_components(graph_nx)
        if len(component) > 1
    ]
    nontrivial.sort(key=lambda members: (-len(members), members))
    for index, members in enumerate(nontrivial, start=1):
        cluster_id = f"scc.{index}"
        summary = {
            "id": cluster_id,
            "size": len(members),
            "members": members,
            "label": f"SCC ({len(members)} nodes)",
        }
        clusters.append(summary)
        for node_id in members:
            memberships[node_id] = summary
    return memberships, clusters


def _edge_payload(edge: Edge, repo_root: Path) -> dict:
    return {
        "from": edge.from_,
        "to": edge.to,
        "kind": edge.kind.value,
        "description": edge.description,
        "tex": _tex_payload(edge.tex, repo_root),
    }


def _tex_payload(ref: TexRef | None, repo_root: Path) -> dict | None:
    if ref is None:
        return None
    exists = (repo_root / ref.file).exists()
    return {
        "file": ref.file,
        "label": ref.label,
        "href": _tex_href(ref.file, ref.label),
        "exists": exists,
    }


def _code_payload(ref: CodeRef, repo_root: Path) -> dict:
    label = f"{ref.path}::{ref.symbol}" if ref.symbol else ref.path
    if ref.line is not None:
        label += f":{ref.line}"
    path = repo_root / ref.path
    if ref.line is not None:
        line_start = line_end = ref.line
    else:
        line_start, line_end = _symbol_range(path, ref.symbol)
    return {
        "path": ref.path,
        "symbol": ref.symbol,
        "label": label,
        "href": _code_href(ref.path, ref.symbol, ref.line),
        "vscodeHref": _vscode_href(path, line_start),
        "lineStart": line_start,
        "lineEnd": line_end,
        "exists": (repo_root / ref.path).exists(),
    }


def _output_payload(ref: OutputRef, repo_root: Path) -> dict:
    return {"path": ref.path, "href": _href(ref.path), "exists": (repo_root / ref.path).exists()}


def _href(path: str, label: str | None = None) -> str:
    href = "refs/" + Path(path).as_posix()
    if label:
        href += f"#{label}"
    return href


def _tex_href(path: str, label: str | None = None) -> str:
    href = _tex_render_path(Path(path)).as_posix()
    if label:
        href += f"#{label}"
    return href


def _tex_render_path(path: Path) -> Path:
    return Path("tex") / path.with_suffix(".html")


def _code_href(path: str, symbol: str | None = None, line: int | None = None) -> str:
    href = _code_render_path(Path(path)).as_posix()
    if line is not None:
        href += f"#L{line}"
    elif symbol:
        href += f"#{symbol}"
    return href


def _code_render_path(path: Path) -> Path:
    return Path("code") / path.with_suffix(path.suffix + ".html")


def _vscode_href(path: Path, line: int | None = None) -> str:
    normalized = path.resolve().as_posix()
    suffix = f":{line}" if line else ""
    return "vscode://file/" + quote(normalized + suffix, safe="/:")


def _symbol_range(path: Path, symbol: str | None) -> tuple[int | None, int | None]:
    if symbol is None or not path.exists() or path.suffix != ".py":
        return None, None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None, None
    for item in tree.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and item.name == symbol:
            return item.lineno, getattr(item, "end_lineno", item.lineno)
    return None, None


def _symbol_ranges_for_file(text: str, path: str) -> dict[str, tuple[int, int]]:
    if not path.endswith(".py"):
        return {}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    ranges: dict[str, tuple[int, int]] = {}
    for item in tree.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            ranges[item.name] = (item.lineno, getattr(item, "end_lineno", item.lineno))
    return ranges


def _render_code_document(title: str, style_href: str, text: str) -> str:
    ranges = _symbol_ranges_for_file(text, title)
    line_to_symbol = {start: symbol for symbol, (start, _) in ranges.items()}
    highlighted_lines = {
        line
        for start, end in ranges.values()
        for line in range(start, end + 1)
    }
    rendered_lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        anchors = ""
        if number in line_to_symbol:
            anchors = f'<a class="source-anchor" id="{escape(line_to_symbol[number])}"></a>'
        classes = "source-line highlighted" if number in highlighted_lines else "source-line"
        rendered_lines.append(
            f'{anchors}<span id="L{number}" class="{classes}">'
            f'<span class="line-number">{number}</span>'
            f'<code>{escape(line)}</code>'
            f"</span>"
        )
    body = "\n".join(rendered_lines)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <link rel="stylesheet" href="{escape(style_href)}">
  </head>
  <body class="code-page">
    <header class="code-header">
      <h1>{escape(title)}</h1>
    </header>
    <pre class="source-view">{body}</pre>
  </body>
</html>
"""


def _render_tex_document(
    title: str,
    style_href: str,
    text: str,
    *,
    pdf_name: str | None = None,
    render_error: str | None = None,
) -> str:
    if pdf_name:
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <link rel="stylesheet" href="{escape(style_href)}">
    <style>
      body {{ background: #fff; margin: 0; }}
      .derivation-frame {{ display: block; width: 100%; height: 100vh; border: 0; }}
      .pdf-link {{ position: fixed; right: 12px; top: 10px; z-index: 2; background: #fff; padding: 6px 9px; border: 1px solid #d9e0e8; border-radius: 4px; }}
    </style>
  </head>
  <body>
    <a class="pdf-link" href="{escape(pdf_name)}">Open PDF</a>
    <iframe class="derivation-frame" src="{escape(pdf_name)}#view=FitH" title="Rendered derivation"></iframe>
  </body>
</html>
"""

    body = _tex_to_html(text)
    error_text = escape(render_error or "A local TeX compiler was not available.")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <script>
      window.MathJax = {{
        tex: {{ inlineMath: [["\\\\(", "\\\\)"]], displayMath: [["\\\\[", "\\\\]"]], processEnvironments: true }},
        svg: {{ fontCache: "global" }},
        startup: {{
          ready() {{
            MathJax.startup.defaultReady();
            MathJax.startup.promise.then(() => document.documentElement.classList.add("math-ready"));
          }}
        }}
      }};
      window.setTimeout(() => {{
        if (!document.documentElement.classList.contains("math-ready")) document.documentElement.classList.add("math-failed");
      }}, 8000);
    </script>
    <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
    <link rel="stylesheet" href="{escape(style_href)}">
    <style>
      body {{ background: #fff; padding: 24px; max-width: 920px; margin: 0 auto; }}
      .math {{ overflow-x: auto; }}
      .anchor {{ scroll-margin-top: 20px; }}
      .math-document {{ visibility: hidden; }}
      .math-ready .math-document {{ visibility: visible; }}
      .render-failure {{ display: none; padding: 16px; border: 1px solid #dc2626; color: #991b1b; }}
      .math-failed .render-failure {{ display: block; }}
    </style>
  </head>
  <body>
    <div class="render-failure">Could not render this derivation locally or load the browser math renderer. {error_text}</div>
    <main class="math-document">{body}</main>
  </body>
</html>
"""


def _tex_to_html(text: str) -> str:
    text = re.sub(r"\\documentclass(?:\[[^\]]*\])?\{[^}]+\}", "", text)
    text = re.sub(r"\\usepackage(?:\[[^\]]*\])?\{[^}]+\}", "", text)
    text = re.sub(r"\\title\{([^}]*)\}", r"<h1>\1</h1>", text)
    text = re.sub(r"\\author\{([^}]*)\}", r"<p>\1</p>", text)
    text = re.sub(r"\\date\{[^}]*\}", "", text)
    text = text.replace(r"\begin{document}", "").replace(r"\end{document}", "")
    text = text.replace(r"\maketitle", "")
    text = re.sub(r"\\input\{([^}]+)\}", r"\n\nIncluded file: \1\n\n", text)
    text = re.sub(r"\\section\*?\{([^}]*)\}", r"\n\n<h2>\1</h2>\n\n", text)
    text = re.sub(r"\\subsection\*?\{([^}]*)\}", r"\n\n<h3>\1</h3>\n\n", text)
    labels = re.findall(r"\\label\{([^}]*)\}", text)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(r"\\par(?:\s+|(?=[A-Z]))", "\n\n", text)

    math_blocks: list[str] = []

    def stash_math(value: str) -> str:
        math_blocks.append(value)
        return f"\n\n@@MATH{len(math_blocks) - 1}@@\n\n"

    environment_pattern = re.compile(
        r"\\begin\{(align\*?|equation\*?|gather\*?|multline\*?|displaymath)\}([\s\S]*?)\\end\{\1\}"
    )

    def replace_environment(match: re.Match) -> str:
        environment = match.group(1).rstrip("*")
        content = match.group(2).strip()
        if environment in {"equation", "displaymath"}:
            rendered = f"\\[{content}\\]"
        elif environment == "gather":
            rendered = f"\\[\\begin{{gathered}}{content}\\end{{gathered}}\\]"
        else:
            rendered = f"\\[\\begin{{aligned}}{content}\\end{{aligned}}\\]"
        return stash_math(rendered)

    text = environment_pattern.sub(replace_environment, text)
    text = re.sub(r"\\\[[\s\S]*?\\\]", lambda match: stash_math(match.group(0)), text)

    parts = re.split(r"(@@MATH\d+@@|<h[1-3]>.*?</h[1-3]>)", text)
    html_parts: list[str] = []
    html_parts.extend(f'<a class="anchor" id="{escape(label)}"></a>' for label in labels)
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if stripped.startswith("<h"):
            html_parts.append(stripped)
        elif re.fullmatch(r"@@MATH\d+@@", stripped):
            index = int(stripped[6:-2])
            html_parts.append(f'<div class="math">{escape(math_blocks[index])}</div>')
        else:
            paragraphs = [p.strip() for p in stripped.split("\n\n") if p.strip()]
            for paragraph in paragraphs:
                html_parts.append(f"<p>{_render_inline_latex(paragraph)}</p>")
    return "\n".join(html_parts)


def _render_inline_latex(text: str) -> str:
    placeholders: list[str] = []

    def stash(pattern: str, template) -> None:
        nonlocal text

        def replace(match: re.Match) -> str:
            placeholders.append(template(match))
            return f"@@HTML{len(placeholders) - 1}@@"

        text = re.sub(pattern, replace, text)

    stash(r"\\texttt\{([^}]*)\}", lambda match: f"<code>{_latex_text_arg(match.group(1))}</code>")
    stash(r"\\textbf\{([^}]*)\}", lambda match: f"<strong>{_latex_text_arg(match.group(1))}</strong>")
    stash(r"\\emph\{([^}]*)\}", lambda match: f"<em>{_latex_text_arg(match.group(1))}</em>")

    escaped = escape(text)
    for index, value in enumerate(placeholders):
        escaped = escaped.replace(f"@@HTML{index}@@", value)
    return escaped


def _latex_text_arg(text: str) -> str:
    text = text.replace(r"\_", "_").replace(r"\{", "{").replace(r"\}", "}")
    return escape(text)


def _is_test_ref(ref: CodeRef) -> bool:
    normalized = ref.path.replace("\\", "/")
    return normalized.startswith("tests/") or "/tests/" in f"/{normalized}"


def _index_html() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mathgraph</title>
    <link rel="icon" href="data:,">
    <meta http-equiv="Cache-Control" content="no-store">
    <link rel="stylesheet" href="style.css?v=elk-layout-1">
  </head>
  <body>
    <header class="topbar">
      <div>
        <h1 id="project-title">Mathgraph</h1>
      </div>
    </header>
    <main class="layout">
      <section class="graph-pane" aria-label="Graph">
        <svg id="graph-view" role="img" aria-label="Mathgraph dependency graph"></svg>
      </section>
      <section id="detail" class="detail-pane" aria-live="polite"></section>
    </main>
    <noscript>
      <main class="noscript">
        <h2>Graph Data</h2>
        <p><a href="graph.json">Open graph.json</a></p>
      </main>
    </noscript>
    <script src="vendor/elk.bundled.js?v=elk-layout-1"></script>
    <script src="app.js?v=elk-layout-1"></script>
  </body>
</html>
"""


def _style_css() -> str:
    return """:root {
  color-scheme: light;
  --bg: #f5f7fa;
  --panel: #ffffff;
  --ink: #18212b;
  --muted: #667381;
  --line: #d9e0e8;
  --accent: #2563eb;
  --accent-soft: #eaf1ff;
  --green-soft: #e7f6ef;
  --edge: #a5b0bd;
  --edge-active: #1d4ed8;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
  background: var(--panel);
  box-shadow: 0 1px 8px rgba(24, 33, 43, 0.05);
  position: relative;
  z-index: 2;
}

h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
}

.layout {
  display: grid;
  grid-template-columns: minmax(620px, 1fr) minmax(330px, 430px);
  min-height: calc(100vh - 73px);
}

.graph-pane {
  position: relative;
  min-height: calc(100vh - 73px);
  overflow: hidden;
  background:
    radial-gradient(circle at 20px 20px, rgba(37, 99, 235, 0.07) 0 1px, transparent 1px 100%),
    linear-gradient(180deg, #f7f9fc 0%, #edf2f8 100%);
  background-size: 28px 28px, auto;
}

#graph-view {
  width: 100%;
  height: calc(100vh - 73px);
  display: block;
  cursor: grab;
  user-select: none;
  touch-action: none;
}

#graph-view.dragging {
  cursor: grabbing;
}

.graph-cluster-card {
  fill: rgba(255, 255, 255, 0.82);
  stroke: rgba(148, 163, 184, 0.8);
  stroke-width: 1.2;
  filter: drop-shadow(0 14px 24px rgba(24, 33, 43, 0.08));
}

.graph-cluster.active .graph-cluster-card,
.graph-cluster.neighbor .graph-cluster-card {
  stroke: rgba(37, 99, 235, 0.9);
  stroke-width: 1.8;
}

.graph-cluster.dimmed {
  opacity: 0.2;
}

.cluster-label {
  fill: #526171;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.graph-edge {
  stroke: var(--edge);
  stroke-width: 1.7;
  fill: none;
  cursor: pointer;
  opacity: 0.82;
}

.graph-edge.active {
  stroke: var(--edge-active);
  stroke-width: 2.9;
  opacity: 1;
}

.graph-edge.hovered {
  stroke: #3b82f6;
  stroke-width: 2.3;
  opacity: 1;
}

.graph-edge.dimmed {
  opacity: 0.18;
}

.edge-hit {
  stroke: transparent;
  stroke-width: 18;
  fill: none;
  cursor: pointer;
}

.edge-label {
  fill: #4d5966;
  font-size: 11px;
  pointer-events: none;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.8);
  stroke-width: 4px;
  opacity: 0;
  transition: opacity 120ms ease;
}

.edge-label.visible {
  opacity: 1;
}

.graph-node .node-card {
  fill: rgba(255, 255, 255, 0.98);
  stroke: rgba(205, 213, 224, 0.95);
  stroke-width: 1.5;
  filter: drop-shadow(0 4px 10px rgba(24, 33, 43, 0.2));
  cursor: pointer;
}

.graph-node .node-accent {
  opacity: 0.98;
}

.graph-node.active .node-card {
  stroke: #111827;
  stroke-width: 2.4;
}

.graph-node.hovered .node-card,
.graph-node.neighbor .node-card {
  stroke: var(--accent);
  stroke-width: 2.2;
}

.graph-node.dimmed {
  opacity: 0.23;
}

.graph-node text {
  pointer-events: none;
}

.graph-node .node-title-image {
  pointer-events: none;
}

.graph-node .node-title-fallback {
  fill: var(--ink);
  font-size: 15px;
  font-weight: 700;
}

.graph-node .node-kind {
  fill: var(--muted);
  font-size: 12px;
  font-weight: 600;
}

.node-button,
.edge-button {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  cursor: pointer;
}

.node-button {
  display: block;
  width: 100%;
  min-height: 58px;
  text-align: left;
  border-radius: 6px;
  padding: 8px 10px;
}

.edge-button {
  display: block;
  width: 100%;
  text-align: left;
  border-radius: 6px;
  padding: 8px 10px;
}

.node-button.active {
  border-color: var(--accent);
  box-shadow: inset 3px 0 0 var(--accent);
}

.node-id {
  display: block;
  font-weight: 650;
}

.node-title {
  display: block;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.inline-title-image {
  display: block;
  max-width: min(100%, 420px);
  max-height: 46px;
  object-fit: contain;
  object-position: left center;
}

.badge {
  display: inline-block;
  margin-top: 5px;
  border-radius: 4px;
  padding: 1px 5px;
  background: var(--green-soft);
  color: #1e6b45;
  font-size: 12px;
}

.legend {
  position: absolute;
  right: 14px;
  bottom: 14px;
  z-index: 1;
  display: grid;
  gap: 5px;
  padding: 10px;
  border: 1px solid rgba(217, 224, 232, 0.9);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 25px rgba(24, 33, 43, 0.08);
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--muted);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.detail-pane {
  padding: 20px;
  overflow: auto;
  background: var(--panel);
  border-left: 1px solid var(--line);
}

.detail-inner {
  max-width: 680px;
}

.detail-pane h2 {
  margin: 0 0 4px;
  font-size: 19px;
  line-height: 1.25;
}

.statement {
  margin: 14px 0 18px;
  max-width: 850px;
  color: var(--ink);
}

.sections {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.section {
  border-top: 1px solid var(--line);
  padding-top: 12px;
}

.section h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.ref-list,
.edge-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.ref-list li,
.edge-list li {
  margin: 0 0 8px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}

.edge-list button {
  margin-top: 6px;
}

a {
  color: var(--accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

.link-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: baseline;
}

.link-label {
  color: var(--muted);
  flex-basis: 100%;
  overflow-wrap: anywhere;
}

.edge-route {
  display: block;
  font-weight: 650;
}

.edge-description,
.empty {
  color: var(--muted);
}

.empty {
  margin: 0;
}

@media (max-width: 780px) {
  .topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .layout,
  .sections {
    grid-template-columns: 1fr;
  }

  .graph-pane,
  #graph-view {
    min-height: 520px;
    height: 520px;
  }
}

.code-page {
  background: #ffffff;
  margin: 0;
}

.code-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
}

.code-header h1 {
  font-size: 16px;
}

.source-view {
  margin: 0;
  padding: 16px 0;
  overflow: auto;
  font: 13px/1.45 Consolas, "Liberation Mono", monospace;
}

.source-line {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  min-height: 19px;
  padding-right: 16px;
}

.source-line:target,
.source-line.highlighted,
.source-anchor:target + .source-line {
  background: #fff8d7;
}

.line-number {
  user-select: none;
  color: #7b8794;
  text-align: right;
  padding-right: 14px;
  border-right: 1px solid #edf0f3;
  margin-right: 12px;
}

.source-line code {
  white-space: pre;
}
"""


def _modern_app_js() -> str:
    return """let graph = null;
let selectedNodeId = null;
let selectedEdgeIndex = null;
let hoveredNodeId = null;
let hoveredEdgeIndex = null;
let transform = { x: 0, y: 0, scale: 1 };
let isPanning = false;
let panStart = null;
let graphLayout = null;
let graphViewport = null;
let selectionFramePending = false;
let transformFramePending = false;
let nodeElements = new Map();
let edgeElements = new Map();
let edgeLabelElements = new Map();
let clusterElements = new Map();

const detail = document.getElementById("detail");
const graphView = document.getElementById("graph-view");

const KIND_ORDER = [
  "variable", "assumption", "objective", "estimator", "approximation",
  "simulator", "experiment", "validation", "figure", "dataset", "test"
];

const KIND_COLORS = {
  variable: "#0ea5e9",
  assumption: "#f97316",
  objective: "#ec4899",
  estimator: "#ef4444",
  approximation: "#14b8a6",
  simulator: "#22c55e",
  experiment: "#64748b",
  validation: "#2563eb",
  figure: "#8b5cf6",
  dataset: "#eab308",
  test: "#475569",
  default: "#94a3b8",
};

fetch("graph.json")
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(async (data) => {
    graph = data;
    selectedNodeId = graph.nodes[0]?.id || null;
    document.getElementById("project-title").textContent = graph.project.title || "Mathgraph";
    if (typeof ELK !== "function") throw new Error("Local elkjs bundle is unavailable.");
    attachGraphGestures();
    await renderGraph();
    renderNodeDetail();
    bindDetailButtons();
  })
  .catch((error) => {
    detail.innerHTML = `<p class="empty">Could not load graph.json: ${escapeHtml(error.message)}</p>`;
  });

async function renderGraph() {
  const layout = await layoutGraph();
  graphLayout = layout;
  graphView.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  const related = relatedIds();
  const legendKinds = Array.from(new Set(graph.nodes.map((node) => node.kind))).sort();
  graphView.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
        <path d="M0,0 L10,4 L0,8 z" fill="#a5b0bd"></path>
      </marker>
      <marker id="arrow-active" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
        <path d="M0,0 L10,4 L0,8 z" fill="#1d4ed8"></path>
      </marker>
    </defs>
    <g id="graph-viewport">
      ${layout.clusters.map((cluster) => renderCluster(cluster, related)).join("")}
      ${graph.edges.map((edge, index) => renderGraphEdge(edge, index, layout.positions, related)).join("")}
      ${graph.nodes.map((node) => renderGraphNode(node, layout.positions.get(node.id), related)).join("")}
      ${legendKinds.map((kind, index) => renderLegendItem(kind, layout.width - 160, layout.height - 26 - index * 20)).join("")}
    </g>
  `;
  graphViewport = document.getElementById("graph-viewport");
  nodeElements = new Map(Array.from(graphView.querySelectorAll(".graph-node")).map((element) => [element.dataset.nodeId, element]));
  edgeElements = new Map(Array.from(graphView.querySelectorAll(".graph-edge")).map((element) => [Number(element.dataset.edgeIndex), element]));
  edgeLabelElements = new Map(Array.from(graphView.querySelectorAll(".edge-label")).map((element) => [Number(element.dataset.edgeIndex), element]));
  clusterElements = new Map(Array.from(graphView.querySelectorAll(".graph-cluster")).map((element) => [element.dataset.clusterId, element]));
  applyGraphTransform();
  updateGraphSelection();
}

async function layoutGraph() {
  const elk = new ELK();
  const groups = buildSccGroups();
  const groupLayouts = await Promise.all(groups.map((group) => layoutGroup(elk, group)));
  const groupById = new Map(groupLayouts.map((group) => [group.id, group]));
  const groupIdByNode = new Map();
  for (const group of groups) {
    group.nodes.forEach((node) => groupIdByNode.set(node.id, group.id));
  }
  const edgeByRoute = new Map();
  graph.edges.forEach((edge, index) => {
    const fromGroup = groupIdByNode.get(edge.from);
    const toGroup = groupIdByNode.get(edge.to);
    if (!fromGroup || !toGroup || fromGroup === toGroup) return;
    const key = `${fromGroup}->${toGroup}`;
    if (!edgeByRoute.has(key)) edgeByRoute.set(key, []);
    edgeByRoute.get(key).push(index);
  });

  const root = await elk.layout({
    id: "mathgraph-root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "70",
      "elk.layered.spacing.nodeNodeBetweenLayers": "120",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.padding": "[top=30,left=30,bottom=30,right=30]",
    },
    children: groupLayouts.map((group) => ({ id: group.id, width: group.width, height: group.height })),
    edges: Array.from(edgeByRoute.entries()).map(([route, edgeIndexes]) => {
      const [source, target] = route.split("->");
      return {
        id: `route:${route}`,
        sources: [source],
        targets: [target],
        labels: [{ text: String(edgeIndexes.length) }],
      };
    }),
  });

  const marginX = 120;
  const marginY = 90;
  const rootChildren = new Map((root.children || []).map((child) => [child.id, child]));
  const positions = new Map();
  const clusters = [];
  for (const group of groupLayouts) {
    const rootNode = rootChildren.get(group.id);
    const baseX = marginX + (rootNode?.x || 0);
    const baseY = marginY + (rootNode?.y || 0);
    if (group.members.length > 1) {
      clusters.push({
        id: group.id,
        x: baseX,
        y: baseY,
        width: group.width,
        height: group.height,
        label: `SCC (${group.members.length} nodes)`,
        members: group.members,
      });
    }
    for (const member of group.members) {
      const local = group.positions.get(member.id);
      if (!local) continue;
      positions.set(member.id, {
        x: baseX + local.x,
        y: baseY + local.y,
        width: local.width,
        height: local.height,
      });
    }
  }

  return {
    positions,
    clusters,
    width: marginX * 2 + (root.width || 900),
    height: marginY * 2 + (root.height || 700),
  };
}

function buildSccGroups() {
  const groups = [];
  const assigned = new Set();
  const graphClusters = Array.isArray(graph.clusters) ? graph.clusters : [];
  graphClusters.forEach((cluster) => {
    const members = cluster.members.map((nodeId) => findNode(nodeId)).filter(Boolean);
    members.forEach((node) => assigned.add(node.id));
    groups.push({ id: cluster.id, nodes: members, cluster });
  });
  graph.nodes
    .filter((node) => !assigned.has(node.id))
    .sort((a, b) => displayName(a).localeCompare(displayName(b)))
    .forEach((node) => {
      groups.push({ id: `node:${node.id}`, nodes: [node], cluster: null });
    });
  return groups;
}

async function layoutGroup(elk, group) {
  const internalEdges = graph.edges.filter((edge) =>
    group.nodes.some((node) => node.id === edge.from) &&
    group.nodes.some((node) => node.id === edge.to)
  );
  const positions = new Map();
  if (group.nodes.length === 1) {
    const only = group.nodes[0];
    const box = nodeBox(only);
    positions.set(only.id, { x: 0, y: 0, width: box.width, height: box.height });
    return {
      id: group.id,
      width: box.width,
      height: box.height,
      positions,
      members: group.nodes,
    };
  }

  const local = await elk.layout({
    id: group.id,
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "26",
      "elk.layered.spacing.nodeNodeBetweenLayers": "38",
      "elk.edgeRouting": "POLYLINE",
      "elk.padding": "[top=12,left=12,bottom=12,right=12]",
    },
    children: group.nodes.map((node) => {
      const box = nodeBox(node);
      return { id: node.id, width: box.width, height: box.height };
    }),
    edges: internalEdges.map((edge, index) => ({
      id: `${group.id}:edge:${index}`,
      sources: [edge.from],
      targets: [edge.to],
    })),
  });

  const paddingX = 26;
  const paddingBottom = 24;
  const headerHeight = 32;
  const paddingTop = 22;
  (local.children || []).forEach((child) => {
    positions.set(child.id, {
      x: paddingX + (child.x || 0),
      y: headerHeight + paddingTop + (child.y || 0),
      width: child.width || nodeBox(findNode(child.id)).width,
      height: child.height || nodeBox(findNode(child.id)).height,
    });
  });

  return {
    id: group.id,
    width: paddingX * 2 + (local.width || 0),
    height: headerHeight + paddingTop + paddingBottom + (local.height || 0),
    positions,
    members: group.nodes,
  };
}

function scheduleGraphTransform() {
  if (transformFramePending) return;
  transformFramePending = true;
  window.requestAnimationFrame(() => {
    transformFramePending = false;
    applyGraphTransform();
  });
}

function applyGraphTransform() {
  if (!graphLayout || !graphViewport) return;
  graphViewport.setAttribute(
    "transform",
    `matrix(${transform.scale} 0 0 ${transform.scale} ${transform.x} ${transform.y})`
  );
}

function screenScale() {
  if (!graphLayout) return { x: 1, y: 1 };
  const rect = graphView.getBoundingClientRect();
  return {
    x: rect.width / Math.max(graphLayout.width, 1),
    y: rect.height / Math.max(graphLayout.height, 1),
  };
}

function normalizeWheelDelta(event) {
  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * 16;
  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * graphView.getBoundingClientRect().height;
  return event.deltaY;
}

function scheduleSelectionUpdate() {
  if (selectionFramePending) return;
  selectionFramePending = true;
  window.requestAnimationFrame(() => {
    selectionFramePending = false;
    updateGraphSelection();
  });
}

function updateGraphSelection() {
  const related = relatedIds();
  const activeClusters = new Set();
  related.nodes.forEach((nodeId) => {
    const cluster = findNode(nodeId)?.cluster;
    if (cluster?.id) activeClusters.add(cluster.id);
  });
  nodeElements.forEach((element, nodeId) => {
    element.classList.toggle("active", selectedNodeId === nodeId);
    element.classList.toggle("hovered", hoveredNodeId === nodeId);
    element.classList.toggle("neighbor", related.active && related.nodes.has(nodeId) && selectedNodeId !== nodeId);
    element.classList.toggle("dimmed", related.active && !related.nodes.has(nodeId));
  });
  edgeElements.forEach((element, edgeIndex) => {
    const active = selectedEdgeIndex === edgeIndex || related.edges.has(edgeIndex);
    const hovered = hoveredEdgeIndex === edgeIndex;
    element.classList.toggle("active", active);
    element.classList.toggle("hovered", hovered);
    element.classList.toggle("dimmed", related.active && !related.edges.has(edgeIndex));
    element.setAttribute("marker-end", `url(#${active || hovered ? "arrow-active" : "arrow"})`);
  });
  edgeLabelElements.forEach((element, edgeIndex) => {
    element.classList.toggle("visible", shouldShowEdgeLabel(edgeIndex));
  });
  clusterElements.forEach((element, clusterId) => {
    element.classList.toggle("active", activeClusters.has(clusterId) && selectedNodeId !== null);
    element.classList.toggle("neighbor", activeClusters.has(clusterId) && selectedNodeId === null && selectedEdgeIndex !== null);
    element.classList.toggle("dimmed", related.active && !activeClusters.has(clusterId));
  });
}

function attachGraphGestures() {
  graphView.addEventListener("click", (event) => {
    const nodeTarget = event.target.closest("[data-node-id]");
    if (nodeTarget) {
      event.stopPropagation();
      selectNode(nodeTarget.dataset.nodeId);
      return;
    }
    const edgeTarget = event.target.closest("[data-edge-index]");
    if (edgeTarget) {
      event.stopPropagation();
      selectEdge(Number(edgeTarget.dataset.edgeIndex));
    }
  });

  graphView.addEventListener("pointermove", (event) => {
    const nodeTarget = event.target.closest("[data-node-id]");
    const edgeTarget = nodeTarget ? null : event.target.closest("[data-edge-index]");
    const nextHoveredNodeId = nodeTarget?.dataset.nodeId || null;
    const nextHoveredEdgeIndex = edgeTarget ? Number(edgeTarget.dataset.edgeIndex) : null;
    if (nextHoveredNodeId === hoveredNodeId && nextHoveredEdgeIndex === hoveredEdgeIndex) return;
    hoveredNodeId = nextHoveredNodeId;
    hoveredEdgeIndex = nextHoveredEdgeIndex;
    scheduleSelectionUpdate();
  });

  graphView.addEventListener("pointerleave", () => {
    if (hoveredNodeId === null && hoveredEdgeIndex === null) return;
    hoveredNodeId = null;
    hoveredEdgeIndex = null;
    scheduleSelectionUpdate();
  });

  graphView.addEventListener("wheel", (event) => {
    event.preventDefault();
    const delta = normalizeWheelDelta(event);
    const factor = Math.exp(-delta * 0.002);
    zoomBy(factor, event.clientX, event.clientY);
  }, { passive: false });

  graphView.addEventListener("pointerdown", (event) => {
    if (event.target.closest("[data-node-id], [data-edge-index]")) return;
    isPanning = true;
    graphView.classList.add("dragging");
    panStart = { x: event.clientX, y: event.clientY, tx: transform.x, ty: transform.y };
    graphView.setPointerCapture(event.pointerId);
  });

  graphView.addEventListener("pointermove", (event) => {
    if (!isPanning || !panStart) return;
    const scale = screenScale();
    transform.x = panStart.tx + (event.clientX - panStart.x) / scale.x;
    transform.y = panStart.ty + (event.clientY - panStart.y) / scale.y;
    scheduleGraphTransform();
  });

  graphView.addEventListener("pointerup", (event) => {
    isPanning = false;
    panStart = null;
    graphView.classList.remove("dragging");
    try { graphView.releasePointerCapture(event.pointerId); } catch (error) {}
  });
}

function zoomBy(factor, clientX = null, clientY = null) {
  const oldScale = transform.scale;
  const newScale = oldScale * factor;
  if (!Number.isFinite(newScale) || newScale <= 0) return;
  if (newScale === oldScale) return;

  const rect = graphView.getBoundingClientRect();
  const scale = screenScale();
  const screen = clientX === null || clientY === null
    ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
    : { x: clientX, y: clientY };
  const localX = screen.x - rect.left;
  const localY = screen.y - rect.top;
  const anchor = screenToGraphPoint(screen.x, screen.y);

  transform.scale = newScale;
  transform.x = localX / scale.x - anchor.x * newScale;
  transform.y = localY / scale.y - anchor.y * newScale;
  scheduleGraphTransform();
}

function screenToGraphPoint(clientX, clientY) {
  const rect = graphView.getBoundingClientRect();
  const scale = screenScale();
  return {
    x: (((clientX - rect.left) / scale.x) - transform.x) / transform.scale,
    y: (((clientY - rect.top) / scale.y) - transform.y) / transform.scale,
  };
}

function relatedIds() {
  const nodes = new Set();
  const edges = new Set();
  if (selectedNodeId) {
    nodes.add(selectedNodeId);
    graph.edges.forEach((edge, index) => {
      if (edge.from === selectedNodeId || edge.to === selectedNodeId) {
        nodes.add(edge.from);
        nodes.add(edge.to);
        edges.add(index);
      }
    });
  }
  if (selectedEdgeIndex !== null) {
    const edge = graph.edges[selectedEdgeIndex];
    if (edge) {
      nodes.add(edge.from);
      nodes.add(edge.to);
      edges.add(selectedEdgeIndex);
    }
  }
  return { active: selectedNodeId !== null || selectedEdgeIndex !== null, nodes, edges };
}

function renderCluster(cluster, related) {
  const active = related.nodes.size > 0 && cluster.members.some((member) => related.nodes.has(member.id));
  const dimmed = related.active && !active;
  return `<g class="graph-cluster ${active ? "active" : ""} ${dimmed ? "dimmed" : ""}" data-cluster-id="${escapeAttr(cluster.id)}">
    <rect class="graph-cluster-card" x="${cluster.x}" y="${cluster.y}" width="${cluster.width}" height="${cluster.height}" rx="20"></rect>
    <text class="cluster-label" x="${cluster.x + 18}" y="${cluster.y + 22}">${escapeHtml(cluster.label)}</text>
  </g>`;
}

function renderGraphEdge(edge, index, positions, related) {
  const from = positions.get(edge.from);
  const to = positions.get(edge.to);
  if (!from || !to) return "";
  const start = edgeAnchor(from, to);
  const end = edgeAnchor(to, from);
  const deltaY = Math.abs(end.y - start.y);
  const controlOffset = Math.max(38, Math.min(120, deltaY * 0.55));
  const path = `M${start.x},${start.y} C${start.x},${start.y + controlOffset} ${end.x},${end.y - controlOffset} ${end.x},${end.y}`;
  const labelX = (start.x + end.x) / 2;
  const labelY = (start.y + end.y) / 2 - 9;
  const active = selectedEdgeIndex === index || related.edges.has(index) ? "active" : "";
  const dimmed = related.active && !related.edges.has(index) ? "dimmed" : "";
  const hovered = hoveredEdgeIndex === index ? "hovered" : "";
  const marker = active || hovered ? "arrow-active" : "arrow";
  return `<g data-edge-index="${index}">
    <path class="edge-hit" d="${path}" data-edge-index="${index}"></path>
    <path class="graph-edge ${active} ${hovered} ${dimmed}" d="${path}" marker-end="url(#${marker})" data-edge-index="${index}"></path>
    <text class="edge-label ${shouldShowEdgeLabel(index) ? "visible" : ""}" data-edge-index="${index}" x="${labelX}" y="${labelY}">${escapeHtml(edge.kind)}</text>
  </g>`;
}

function renderGraphNode(node, position, related) {
  if (!position) return "";
  const active = selectedNodeId === node.id ? "active" : "";
  const hovered = hoveredNodeId === node.id ? "hovered" : "";
  const neighbor = related.active && related.nodes.has(node.id) && selectedNodeId !== node.id ? "neighbor" : "";
  const dimmed = related.active && !related.nodes.has(node.id) ? "dimmed" : "";
  const box = nodeBox(node);
  const accent = kindColor(node.kind);
  return `<g class="graph-node ${active} ${hovered} ${neighbor} ${dimmed}" transform="translate(${position.x},${position.y})" data-node-id="${escapeAttr(node.id)}">
    <rect class="node-card" width="${box.width}" height="${box.height}" rx="16"></rect>
    <rect class="node-accent" width="8" height="${box.height}" rx="16" fill="${accent}"></rect>
    <circle cx="24" cy="24" r="7" fill="${accent}"></circle>
    ${node.titleImage
      ? `<image class="node-title-image" href="${escapeAttr(node.titleImage)}" x="40" y="13" width="${box.titleWidth}" height="${box.titleHeight}" preserveAspectRatio="xMinYMin meet"></image>`
      : `<text class="node-title-fallback" x="40" y="32">${escapeHtml(shorten(displayName(node), 34))}</text>`}
    <text class="node-kind" x="40" y="${box.height - 16}">${escapeHtml(node.kind)}</text>
  </g>`;
}

function renderLegendItem(kind, x, y) {
  return `<g transform="translate(${x},${y})">
    <circle r="5" fill="${kindColor(kind)}"></circle>
    <text class="edge-label" x="12" y="4">${escapeHtml(kind)}</text>
  </g>`;
}

function kindColor(kind) {
  return KIND_COLORS[kind] || KIND_COLORS.default;
}

function nodeBox(node) {
  return {
    width: Number(node.layout?.boxWidth || 190),
    height: Number(node.layout?.boxHeight || 82),
    titleWidth: Number(node.layout?.titleWidth || Math.max(120, displayName(node).length * 7.5)),
    titleHeight: Number(node.layout?.titleHeight || 24),
  };
}

function edgeAnchor(fromRect, toRect) {
  const fromCenter = centerOfRect(fromRect);
  const toCenter = centerOfRect(toRect);
  const dx = toCenter.x - fromCenter.x;
  const dy = toCenter.y - fromCenter.y;
  const halfWidth = fromRect.width / 2;
  const halfHeight = fromRect.height / 2;
  const scale = 1 / Math.max(Math.abs(dx) / halfWidth || 0, Math.abs(dy) / halfHeight || 0, 1);
  return {
    x: fromCenter.x + dx * scale,
    y: fromCenter.y + dy * scale,
  };
}

function centerOfRect(rect) {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
}

function shouldShowEdgeLabel(edgeIndex) {
  if (selectedEdgeIndex === edgeIndex) return true;
  if (hoveredEdgeIndex === edgeIndex) return true;
  if (selectedNodeId) {
    const edge = graph.edges[edgeIndex];
    return edge && (edge.from === selectedNodeId || edge.to === selectedNodeId);
  }
  return false;
}

function findNode(nodeId) {
  return graph.nodes.find((candidate) => candidate.id === nodeId) || null;
}

function renderNodeDetail() {
  const node = findNode(selectedNodeId);
  if (!node) {
    detail.innerHTML = '<p class="empty">No node selected.</p>';
    return;
  }

  detail.innerHTML = `<article class="detail-inner">
    <h2>${renderNodeTitle(node)}</h2>
    <span class="badge">${escapeHtml(node.kind)}</span>
    <p class="empty">${escapeHtml(node.id)}</p>
    <p class="statement">${escapeHtml(node.statement)}</p>
    <div class="sections">
      ${section("TeX", renderTex(node.tex))}
      ${section("Variable Uses", renderStrings(node.uses))}
      ${section("Code", renderRefs(node.code))}
      ${section("Tests", renderRefs(node.tests))}
      ${section("Outputs", renderOutputs(node.outputs))}
      ${section("Incoming", renderEdges(node.incoming, "incoming"))}
      ${section("Outgoing", renderEdges(node.outgoing, "outgoing"))}
    </div>
  </article>`;
  bindDetailButtons();
}

function renderEdgeDetail() {
  const edge = graph.edges[selectedEdgeIndex];
  if (!edge) {
    detail.innerHTML = '<p class="empty">No edge selected.</p>';
    return;
  }
  detail.innerHTML = `<article class="detail-inner">
    <h2>${escapeHtml(edge.from)} -&gt; ${escapeHtml(edge.to)}</h2>
    <span class="badge">${escapeHtml(edge.kind)}</span>
    <p class="statement">${escapeHtml(edge.description)}</p>
    <div class="sections">
      ${section("Derivation", renderTex(edge.tex))}
      ${section("Input Node", renderNodeJump(edge.from))}
      ${section("Result Node", renderNodeJump(edge.to))}
    </div>
  </article>`;
  bindDetailButtons();
}

function renderNodeJump(nodeId) {
  const node = findNode(nodeId);
  if (!node) return `<p class="empty">${escapeHtml(nodeId)}</p>`;
  return `<button class="node-button" type="button" data-jump-node="${escapeAttr(node.id)}">
    <span class="node-id">${renderNodeTitle(node)}</span>
    <span class="node-title">${escapeHtml(node.id)}</span>
  </button>`;
}

function selectNode(nodeId) {
  selectedNodeId = nodeId;
  selectedEdgeIndex = null;
  scheduleSelectionUpdate();
  renderNodeDetail();
}

function selectEdge(edgeIndex) {
  selectedEdgeIndex = edgeIndex;
  selectedNodeId = null;
  scheduleSelectionUpdate();
  renderEdgeDetail();
}

function bindDetailButtons() {
  detail.querySelectorAll("[data-jump-node]").forEach((button) => {
    button.addEventListener("click", () => selectNode(button.dataset.jumpNode));
  });
  detail.querySelectorAll("[data-jump-edge]").forEach((button) => {
    button.addEventListener("click", () => selectEdge(Number(button.dataset.jumpEdge)));
  });
}

function section(title, body) {
  return `<section class="section"><h3>${escapeHtml(title)}</h3>${body}</section>`;
}

function renderTex(tex) {
  if (!tex) return '<p class="empty">none</p>';
  if (!tex.exists) {
    return `<ul class="ref-list"><li>${escapeHtml(tex.file)}#${escapeHtml(tex.label)} <span class="empty">(not generated yet)</span></li></ul>`;
  }
  return `<ul class="ref-list"><li><a href="${escapeAttr(tex.href)}">Rendered derivation</a><div class="link-label">${escapeHtml(tex.file)}#${escapeHtml(tex.label)}</div></li></ul>`;
}

function renderRefs(refs) {
  if (!refs || refs.length === 0) return '<p class="empty">none</p>';
  return `<ul class="ref-list">${refs.map((ref) => {
    if (!ref.exists) {
      return `<li>${escapeHtml(ref.label)} <span class="empty">(not generated yet)</span></li>`;
    }
    return `<li>
      <div class="link-label">${escapeHtml(ref.label)}${formatLines(ref)}</div>
      <a href="${escapeAttr(ref.href)}">Highlighted source</a>
      <a href="${escapeAttr(ref.vscodeHref)}">Open in VS Code</a>
    </li>`;
  }).join("")}</ul>`;
}

function renderOutputs(outputs) {
  if (!outputs || outputs.length === 0) return '<p class="empty">none</p>';
  return `<ul class="ref-list">${outputs.map((output) => {
    return `<li>${renderMaybeLink(output.href, output.path, output.exists)}</li>`;
  }).join("")}</ul>`;
}

function renderStrings(items) {
  if (!items || items.length === 0) return '<p class="empty">none</p>';
  return `<ul class="ref-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderEdges(edges, direction) {
  if (!edges || edges.length === 0) return '<p class="empty">none</p>';
  return `<ul class="edge-list">${edges.map((edge) => {
    const edgeIndex = graph.edges.findIndex((candidate) =>
      candidate.from === edge.from &&
      candidate.to === edge.to &&
      candidate.kind === edge.kind &&
      candidate.description === edge.description
    );
    const neighbor = direction === "incoming" ? edge.from : edge.to;
    const tex = edge.tex ? renderTexInline(edge.tex) : "none";
    return `<li>
      <span class="edge-route">${escapeHtml(nodeTitle(edge.from))} --${escapeHtml(edge.kind)}--&gt; ${escapeHtml(nodeTitle(edge.to))}</span>
      <p class="edge-description">${escapeHtml(edge.description)}</p>
      <div>TeX: ${tex}</div>
      <button class="edge-button" type="button" data-jump-edge="${edgeIndex}">Highlight edge</button>
      <button class="edge-button" type="button" data-jump-node="${escapeAttr(neighbor)}">Highlight ${escapeHtml(nodeTitle(neighbor))}</button>
    </li>`;
  }).join("")}</ul>`;
}

function renderTexInline(tex) {
  if (!tex.exists) {
    return `${escapeHtml(tex.file)}#${escapeHtml(tex.label)} <span class="empty">(not generated yet)</span>`;
  }
  return `<a href="${escapeAttr(tex.href)}">Rendered derivation</a> <span class="empty">${escapeHtml(tex.file)}#${escapeHtml(tex.label)}</span>`;
}

function formatLines(ref) {
  if (!ref.lineStart) return "";
  if (ref.lineStart === ref.lineEnd) return ` line ${ref.lineStart}`;
  return ` lines ${ref.lineStart}-${ref.lineEnd}`;
}

function renderMaybeLink(href, label, exists) {
  if (exists) return `<a href="${escapeAttr(href)}">${escapeHtml(label)}</a>`;
  return `${escapeHtml(label)} <span class="empty">(not generated yet)</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function shorten(value, maxLength) {
  const text = String(value ?? "");
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}

function nodeTitle(nodeId) {
  const node = findNode(nodeId);
  return node ? displayName(node) : nodeId;
}

function displayName(node) {
  return node.displayLabel || node.title || node.id;
}

function renderNodeTitle(node) {
  if (node.titleImage) {
    return `<img class="inline-title-image" src="${escapeAttr(node.titleImage)}" alt="${escapeAttr(displayName(node))}">`;
  }
  return escapeHtml(displayName(node));
}
"""


def _app_js() -> str:
    return _modern_app_js()

