# Mathgraph Rendering Requirements

Use this protocol whenever creating or changing graph titles, TeX references, derivations, or the rendered graph.

## Node Titles

- Write meaningful one-line equation titles inside `\(...\)` when the object has a genuine one-line definition.
- Keep title TeX compatible with Matplotlib mathtext so `mathgraph render` can create a local SVG. Prefer standard commands such as `\mathbb`, `\mathbf`, `\boldsymbol`, superscripts, subscripts, fractions, and common operators.
- Use a concise text title when the mathematics is inherently multiline or cannot be represented reliably by the title renderer.
- Never depend on browser-time MathJax for graph-node titles. The rendered graph must use the static title asset from `web/math/nodes/`.
- When layout depends on label geometry, measure the rendered SVG once and serialize the title/box dimensions into the graph payload instead of hard-coding browser-side label sizes.

## Graph Viewer Layout

- Treat the graph viewer as a graph-owned output. When rendered-graph structure or interaction changes, update the viewer/output node, its declaration TeX, and any derivation that explains the rendering contract.
- Do not force cyclic graphs through a DAG-only longest-path layout. Condense strongly connected components first, lay out the condensed DAG, and then place member nodes inside each SCC cluster separately.
- Prefer box-aware node layout over point anchors with floating labels. Edges should attach to node boundaries computed from measured width and height.
- Keep layout dependencies local and reproducible. If a browser layout library is required, vendor a local asset and load it from the rendered site instead of depending on a network CDN.
- Reduce edge-label clutter by default. Prefer interaction-gated labels or similar progressive disclosure over always-visible labels that overlap nodes and edges.
- When changing render-time assets or payload structure, update renderer tests to assert the new contract rather than the previous implementation details.

## Derivation Files

- Keep exactly one distinct derivation in each TeX file. Multiple edges may reference its same canonical label.
- Put at most one `\\label` in an `amsmath` equation environment.
- Make each derivation standalone-compilable. Either include a complete document preamble or use commands supported by the renderer's standard `article` preamble with `amsmath`, `amssymb`, `bm`, and `mathtools`.
- Define project-specific macros inside the same derivation file. Do not rely on an aggregate project preamble or another derivation file.
- Use valid display environments such as `equation`, `align`, `gather`, and `multline`; keep prose outside math environments.
- A rendered derivation link should open the locally compiled PDF embedded in its dedicated HTML page. Browser MathJax is only an explicit fallback when local compilation is unavailable.

## Verification

1. Run `mathgraph render` after graph-title or TeX changes.
2. Inspect `web/render-report.json`.
3. Require every node title to have status `rendered`.
4. When a local TeX compiler is available, require every `kind: derivation` entry to be `compiled` or `cached`; fix compilation errors instead of accepting raw TeX.
5. Serve `web/`, then verify that zooming, panning, selecting, and hovering do not replace title-image DOM or reveal TeX source.
6. Verify that cyclic subgraphs remain compact, node boxes do not overlap nearby titles or edges, and interaction-gated edge labels only appear for the intended hover/selection states.
7. Open representative rendered-derivation links and verify equations, headings, paragraphs, and long display blocks visually.
