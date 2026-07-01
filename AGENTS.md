# Repository Rules for Codex

This repository is mathgraph-centered.

Before editing code:

1. Identify the relevant mathgraph node or nodes.
2. If changing mathematical behavior, run or inspect `mathgraph impact <node-id>`.
3. Update the graph before or together with code changes.
4. Every nontrivial function must implement, approximate, validate, simulate, test, or generate output for a mathgraph node.
5. Every estimator must have a validation path.
6. Every edge expressing a mathematical relationship must have a TeX derivation reference.
7. Variables are the only primitive mathematical nodes. Each variable node contains exactly one variable, declares only its existence and domain, and uses the variable-and-domain equation as its title.
8. Every non-variable node must have incoming dependencies that specify it.
9. If a non-variable node uses a mathematical object, declare it in `uses` and make sure that object is an upstream variable node.
10. Every node must have an exact code reference to every source line where its mathematical object is used; symbol references do not replace line-level use-site references.
11. Use a meaningful one-line defining equation as a node title when possible; otherwise use a concise description. Equation titles must render to stable local SVG assets, never interaction-time source text.
12. Store each distinct derivation in its own standalone-compilable TeX file so its link shows a local rendered artifact, never raw TeX.
13. After `mathgraph render`, inspect `web/render-report.json` and fix title or derivation fallbacks when local renderers are available.
14. Do not add orphan code.
15. Do not silently change model assumptions.
16. Keep mathgraph-owned TeX and initialization artifacts under `mathgraph/`, including `mathgraph/paper/...`.
17. If the user invokes `/mathgraph init`, use source-focused indexed review by default, include generated evidence only for explicit `/mathgraph init --include-generated`, use complete file review only for explicit `/mathgraph init --full-review`, and never escalate automatically.
18. Do not claim initialization complete while `mathgraph index check` reports blocked, missing, or stale evidence.
19. After changes, run:
   - `mathgraph check`
   - `mathgraph orphans`
   - relevant tests
   - relevant experiments if behavior changed
20. Report:
   - changed graph nodes
   - changed TeX labels
   - changed code symbols
   - changed tests
   - downstream affected nodes
