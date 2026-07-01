# Mathgraph Specification

`graph.yaml` is the local source of truth for mathematical nodes, dependency edges, TeX references, code references, tests, experiments, and declared outputs.

Variables are the only primitive mathematical nodes. They declare existence and domain only. Every non-variable node must have incoming dependencies and should declare primitive variable dependencies in `uses`.

`mathgraph check` verifies edge endpoints, references, implementation symbols, output paths, and the primitive-variable invariant.
