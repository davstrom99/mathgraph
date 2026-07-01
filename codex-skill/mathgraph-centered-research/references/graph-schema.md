# Mathgraph Schema Reference

## Node Kinds

Common node kinds:

- `variable`: primitive declaration of exactly one mathematical variable. It defines existence and domain only, not distributions, independence assumptions, or model properties.
- `assumption`: explicit mathematical or modeling assumption, including priors, likelihood definitions, posterior distribution declarations, and observation-model assumptions.
- `objective`: optimization objective.
- `estimator`: estimator with an implementation and validation path.
- `approximation`: numerical or approximate version of an unavailable exact object.
- `simulator`: data-generation routine.
- `validation`: empirical or analytical validation check.
- `experiment`: executable experiment producing declared outputs.
- `figure`: figure or visual result.
- `dataset`: dataset or data artifact.
- `test`: explicit test artifact when needed.

Prefer coarse nodes. Do not create one node for every symbol or line of code.

Variables are the only primitive mathematical nodes. A variable node may have no incoming edges. Every non-variable node must have incoming dependencies that specify it.

Random variables require two concepts:

- variable node: `beta in R^p`
- assumption node: `beta ~ N(0, tau^2 I)`

Do not encode distributions or model assumptions inside variable nodes. Title a variable node with its variable-and-domain equation, such as `\(\beta \in \mathbb{R}^d\)`, and do not combine multiple variables in one variable node.

For every node kind, use a meaningful one-line defining equation as `title` when one exists. Use renderer-compatible delimiters, such as `\(...\)`, so `mathgraph render` creates a stable local SVG rather than typesetting during interaction. Use a concise descriptive title only for multiline mathematics or objects without an honest one-line equation.

## Edge Kinds

Common edge kinds:

- `defines`: source object defines part of target.
- `assumes`: target relies on source assumption.
- `depends_on`: target depends on source.
- `derives`: target is mathematically derived from source.
- `implements`: code implements mathematical object.
- `approximates`: target approximates source or an unavailable exact object.
- `validates`: target validates source.
- `tests`: target tests or executes source.
- `generates`: source generates target output.
- `uses`: target uses source.
- `affects`: source affects target.

Every mathematical edge must have a TeX derivation reference. Store each distinct derivation in its own standalone-compilable TeX file; multiple edges may reuse the same file and canonical label when they represent the same argument. Never point derivation links into a project-wide aggregate file.

## Expected Fields

Project:

```yaml
project:
  id: linear_bayes_demo
  title: Linear Bayesian Regression Demo
  tex_root: mathgraph/paper/main.tex
  repo_root: .
  code_roots:
    - src
    - experiments
    - tests
```

Node:

```yaml
- id: estimator.beta_map
  kind: estimator
  title: MAP estimator for beta
  display_label: "β̂_MAP = μₙ"
  symbol: "\\hat{\\beta}_{MAP}"
  statement: "The MAP estimator minimizes the negative log posterior."
  uses: [var.X, var.y, param.beta, param.sigma, param.tau]
  tex:
    file: mathgraph/paper/declarations/estimator_beta_map.tex
    label: estimator:beta-map
  code:
    - path: src/linear_bayes/estimators.py
      symbol: beta_map_closed_form
    - path: src/linear_bayes/estimators.py
      line: 42
  outputs:
    - path: results/example.json
```

Edge:

```yaml
- from: likelihood.gaussian
  to: posterior.gaussian_conjugate
  kind: derives
  description: "Combining the Gaussian likelihood with the Gaussian prior yields the conjugate Gaussian posterior."
  tex:
    file: mathgraph/paper/derivations/gaussian_posterior.tex
    label: deriv:gaussian-posterior
```

## Reference Rules

- `tex.file` must exist.
- `tex.label` must exist in that file.
- `code.path` must exist.
- Python `code.symbol` references should resolve by AST inspection.
- `code.line` is a one-based exact source line and must exist in `code.path`.
- Every node must contain one exact `path` plus `line` reference for every source line where the represented mathematical object is used. Include definitions, implementations, callers, tests, experiments, and configuration. Symbol references may be kept for implementation ownership, but do not substitute for exhaustive line references.
- `project.code_roots` optionally controls which Python roots/files `mathgraph orphans` scans.
- `project.code_exclude` optionally excludes path globs or path parts from `mathgraph orphans`.
- Output paths should be declared on experiment or figure nodes before generated files are added.
- Test functions are code references too; attach them to validation, estimator, assumption, objective, approximation, simulator, or experiment nodes as appropriate.
- `display_label` is optional. When present, keep it consistent with the title. Equation titles should use the renderer-compatible mathtext subset and remain short enough for the graph view.
- `uses` is optional but strongly preferred for non-variable nodes. It lists primitive variable node IDs or symbols used by the node. If omitted, `mathgraph check` falls back to parsing simple symbols from `statement`.
- Every item in `uses` must resolve to a variable node that is upstream of the node through directed edges.
- Non-variable nodes with no incoming edges fail `mathgraph check`.
