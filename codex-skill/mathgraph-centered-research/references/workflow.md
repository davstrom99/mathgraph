# Mathgraph Everyday Workflow

## Everyday Usage

Use the graph as the control plane for mathematical research code:

- TeX explains mathematical objects and derivations for humans.
- Code implements, simulates, validates, tests, or generates outputs.
- `mathgraph/graph.yaml` connects mathematical identity, dependency, traceability, and change impact.

Common commands:

```bash
mathgraph check
mathgraph orphans
mathgraph node <node-id>
mathgraph impact <node-id>
mathgraph impact <node-id> --verbose
mathgraph coverage
mathgraph render
pytest
```

Use `mathgraph node <node-id>` before editing a focused component. Use `mathgraph impact <node-id>` before changing mathematical behavior. Use `mathgraph coverage` to find missing implementation, validation, output, or suspicious references. If the request changes rendered-graph behavior, keep the viewer/output node in scope together with the renderer code.

## Full Onboarding With `/mathgraph init`

When the user invokes `/mathgraph init`, treat it as a complete Codex workflow:

1. Read `init-index.md` and run `mathgraph init` if needed.
2. Use source-focused indexed review by default, `--include-generated` only when explicit, and full review only for an explicit `/mathgraph init --full-review` invocation.
3. Start with `mathgraph index dossier`, inspect every authoritative file, aggregate generated families, and resolve `mathgraph/INIT_DRAFT.yaml`.
4. Write `mathgraph/INIT_REPORT.md`.
5. Build the initial graph and one TeX file per distinct derivation; reuse it for edges sharing the same argument.
6. Attach existing code, tests, outputs, datasets, and experiments. Record every use site of every node as an exact `path` and `line` code reference.
7. Run `mathgraph check`, `mathgraph orphans`, `mathgraph coverage`, `pytest` when available, and `mathgraph render`.
8. Report the initialized graph and unresolved questions.

The CLI command `mathgraph init` only creates the scaffold. The slash command workflow continues through review, graph construction, validation, and rendering.

## Starting A Task

1. Read `AGENTS.md` if present.
2. If `mathgraph/graph.yaml` does not exist, run `mathgraph init`.
3. During initialization, keep mathgraph artifacts under `mathgraph/`; preserve existing project files, and append mathgraph guidance to `AGENTS.md` if it already exists.
4. For `/mathgraph init`, follow `init-index.md`, complete the indexed or explicitly requested full review, mark the checklist, write `mathgraph/INIT_REPORT.md`, then create the initial graph.
5. Inspect `mathgraph/graph.yaml`.
6. Identify the graph node or nodes named in the request.
7. If the request is phrased in code terms, map the code symbol back to its graph node.
8. Inspect the node's TeX, code, tests, outputs, incoming edges, and outgoing edges.
9. For behavior or assumption changes, run `mathgraph impact <node-id>` and keep the affected nodes in scope.

Do not begin with code edits when the mathematical object is missing from the graph. Add or update the graph first, or in the same patch as the corresponding TeX/code.

## Making Changes

Keep edits graph-centered:

- Add or update coarse nodes for mathematical objects, estimators, validations, experiments, or outputs.
- If the rendered graph itself changes behavior, add or update a graph-owned viewer/output node and attach the renderer code plus its tests to that node.
- Put detailed mathematical relationships on edges.
- Add a TeX derivation reference for every mathematical edge, with each distinct derivation in its own standalone-compilable TeX file.
- Attach every nontrivial function to a graph node through a code reference.
- Keep exhaustive use-site traceability: every node must reference every source line where its object is used. Use exact `path` plus `line` entries even when a symbol-level implementation reference is also present.
- Keep each variable node to one variable and title it with its domain equation. Prefer a one-line defining equation as the title of any node when that is mathematically honest; otherwise use a concise description.
- Keep placeholder functions explicit and attached to a graph node.
- Treat layout and interaction logic as first-class behavior: SCC condensation, measured node boxes, routing, and render-time assets should not remain orphan UI implementation details.
- Update tests where behavior, validation, or referenced symbols change.

## Finishing A Task

Run the smallest sufficient checks, then broaden when behavior changed:

```bash
mathgraph check
mathgraph orphans
pytest
```

For model, estimator, validation, experiment, or output changes, also run:

```bash
mathgraph impact <changed-node-id>
mathgraph coverage
python experiments/<changed_experiment>.py
mathgraph render
```

Final reports should include changed graph nodes and edges, TeX labels, code symbols, tests, experiments, outputs, commands run, and any limitations.

After rendering, inspect `web/render-report.json`; require stable local node-title SVGs and locally compiled derivations when a TeX compiler is available. See `rendering.md`.
