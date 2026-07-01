---
name: mathgraph-centered-research
description: mathematics-centered research workflow for codebases organized around an explicit graph of mathematical objects, derivations, implementations, tests, experiments, and outputs. use when working in repositories with a mathgraph/graph.yaml file, commands like mathgraph check/impact/coverage/render, TeX derivation references, when asked to implement, modify, validate, or trace code from mathematical model definitions, or when the user invokes /mathgraph init to initialize a complete graph from an existing project.
---

# Mathgraph-Centered Research Workflow

Use this skill when the repository contains a mathgraph specification or when code changes must be grounded in mathematical definitions.

Core philosophy:

- TeX is for human mathematical exposition.
- Code is for execution.
- The graph is for identity, dependency, traceability, and change impact.
- Codex may change code only by respecting the graph.

## Required Workflow

Before editing code:

1. Locate `mathgraph/graph.yaml`.
2. If it does not exist, run `mathgraph init` and work through `mathgraph/INIT_CHECKLIST.md` before proposing the first graph.
3. Identify the relevant graph node or nodes.
4. Inspect each node statement, TeX references, code references, incoming edges, and outgoing edges.
5. If changing behavior, run or reason through `mathgraph impact <node-id>`.
6. Update graph, TeX, code, tests, experiments, and outputs consistently.

Read `references/workflow.md` for everyday task flow, `references/graph-schema.md` when editing graph structure, `references/change-protocol.md` when changing model assumptions, estimators, or experiments, `references/init-index.md` whenever running `/mathgraph init`, and `references/rendering.md` whenever creating or changing titles, TeX, derivations, rendered output, or graph-view layout behavior.

## `/mathgraph init` Protocol

When the user says `/mathgraph init`, perform complete graph onboarding. Read and follow `references/init-index.md` first. Use source-focused indexed review by default, include generated evidence only for explicit `--include-generated`, and use complete file-by-file review only for explicit `--full-review`. Never escalate modes automatically.

After evidence review, resolve `mathgraph/INIT_DRAFT.yaml`, write `mathgraph/INIT_REPORT.md`, construct the graph, add standalone TeX files, generate exhaustive exact-line references with `mathgraph draft-refs`, and run index, graph, orphan, coverage, test, and render validation.

Only pause before graph writing if the user explicitly asks for a proposal-only pass or if mathematical identity is too ambiguous to construct a coherent graph.

## Rules

- Do not add nontrivial code without attaching it to a graph node.
- Keep mathgraph-owned initialization artifacts under `mathgraph/`; init may append mathgraph rules to top-level `AGENTS.md`.
- Do not change mathematical assumptions silently.
- Every estimator must connect to at least one validation node.
- Every mathematical edge must include a TeX derivation reference.
- Prefer semantically atomic, paper-level mathematical nodes. Create a distinct node whenever an object, assumption, transformation, approximation, identity, result, or validation has independent mathematical meaning, can change independently, is reused downstream, or introduces a new validity condition. Keep only purely local algebraic steps inside a derivation.- Keep nodes unambiguous: a node should be specified by its own fields, neighboring nodes, and edge descriptions.
- Initialization is complete only when every nonprimitive mathematical node can be reconstructed from its declared incoming nodes and rendered derivation without consulting implementation code.
- Variables are the only primitive mathematical nodes. Each variable node declares exactly one variable and its domain only.
- Set every variable-node title to the variable-and-domain equation, for example `\(X \in \mathbb{R}^{n \times d}\)`. Put distributions and all other assumptions in separate assumption nodes.
- Give every node exact code references for every source line where its mathematical object is used, including implementations, callers, tests, experiments, and configuration. Use one `code` entry with `path` and `line` per use site; a symbol-level reference does not replace these line references.
- For a node defined by a meaningful one-line equation, use that equation as its title. Use a concise description only when the defining mathematics is multiline or has no honest one-line equation. Write equation titles in renderer-compatible `\(...\)` TeX so `mathgraph render` generates a stable local SVG.
- Store each distinct derivation in its own standalone-compilable TeX file. Reuse the same file and label for edges that rely on the same mathematical argument. Keep one canonical label in each `amsmath` equation.
- Random variables need two concepts: a variable node for the object and an assumption node for its distribution.
- Every non-variable node must have incoming dependencies and must not introduce undefined mathematical objects.
- Use `uses` to declare primitive variable dependencies; `mathgraph check` verifies that each used variable is upstream.
- When adding an alternative model assumption, create a sibling branch over shared upstream variables.
- When introducing an approximation, create an `approximation` node and state exactly what is approximated.
- Do not use Lean, Coq, Agda, Isabelle, or formal theorem proving unless the repository explicitly changes its philosophy.
- When changing rendered-graph behavior, treat the viewer as a graph-owned output: update the viewer/output node, its TeX declaration or derivation, and the render tests in the same patch.

## Standard Commands

Use these when relevant:

```bash
mathgraph check
mathgraph orphans
mathgraph coverage
mathgraph impact <node-id>
mathgraph impact <node-id> --verbose
mathgraph node <node-id>
pytest
```

After graph, TeX, code-reference, or webpage changes:

```bash
mathgraph render
```

After behavior-changing experiments:

```bash
python experiments/<experiment_script>.py
```

## Estimator Implementation Protocol

When asked to implement a new estimator:

1. Create or update the estimator node.
2. Attach TeX declaration and derivation references.
3. Attach the implementation symbol.
4. Add or update a validation node.
5. Add or update an experiment node if the estimator needs empirical behavior checks.
6. Run `mathgraph check`, relevant tests, and relevant experiments.

## Model-Assumption Branch Protocol

When asked to add or change a model assumption:

1. Identify the existing model or assumption node.
2. Add the new model or assumption node as a sibling branch over shared upstream variables.
3. Add or reuse variable nodes for every mathematical object the new assumption uses.
4. Add incoming edges from the variables and assumptions that specify the new branch.
5. Run `mathgraph impact <shared-variable-node-id>` when comparing branch-level downstream effects.
6. Update affected likelihood definitions, posterior computations, objectives, estimators, simulations, validations, experiments, and outputs.
7. Update TeX derivation references.
8. Run checks and tests.

## Change Report

End tasks with:

- graph nodes changed
- graph edges changed, if any
- TeX labels changed
- code symbols changed
- tests changed
- experiments and outputs changed
- downstream nodes affected
- commands run and results
- known limitations
