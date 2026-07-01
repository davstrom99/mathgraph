# Mathgraph Change Protocol

## Adding Model-Assumption Branches

Use this protocol when adding Student-t noise alongside Gaussian noise, changing independence assumptions, changing priors, changing observation models, or otherwise changing mathematical behavior.

1. Identify the existing model or assumption node.
2. Add a new coarse node for the new assumption or model as a sibling branch over shared upstream variables.
3. Add or reuse variable nodes for every mathematical object the new assumption uses.
4. Keep distributional properties in assumption nodes, not variable nodes.
5. Declare primitive variable dependencies in the new node's `uses` field.
6. Add incoming edges from the variables and assumptions that specify the new node.
7. Give each mathematical edge a TeX derivation/explanation reference.
8. Run branch impact from the shared variables when comparing alternatives:

```bash
mathgraph impact <shared-variable-node-id>
mathgraph impact <shared-variable-node-id> --verbose
```

9. Update affected likelihood definitions, posterior computations, objectives, estimators, simulators, validations, experiments, tests, and outputs.
10. Keep alternative branches visible if they remain useful comparisons. Do not silently mutate an old node into a new assumption if downstream artifacts still rely on the old one.
11. Refresh exact line references for every affected node so added, removed, and moved use sites remain exhaustive.

## Adding Estimators

1. Add or update an `estimator` node for exact estimators.
2. Add an `approximation` node for numerical approximations, variational methods, Monte Carlo methods, or non-conjugate MAP approximations.
3. Declare the primitive variables used by the estimator in `uses`.
4. Make sure those variables are upstream through the likelihood, prior, posterior, objective, or other incoming dependencies.
5. Attach TeX for the estimator definition or objective.
6. Attach the implementation symbol.
7. Add or update validation coverage.
8. Add an experiment node if empirical behavior matters.
9. Run `mathgraph check`, `mathgraph orphans`, `pytest`, and relevant experiments.
10. Add exact `path` plus `line` references for every estimator use site, not only its defining symbol.

Estimator nodes should not pretend that numerical approximations are closed-form posterior results. Put the approximation status in the node statement and edge description.

## Adding Experiments

1. Add an `experiment` node with a clear statement.
2. Attach the script entry point, usually `experiments/<name>.py::main`.
3. Declare every generated output path before writing it.
4. Add a `tests` or `generates` edge from the validation/estimator/model node to the experiment node as appropriate.
5. Give the edge a TeX reference explaining what the experiment checks, stored in a standalone file containing only that derivation.
6. Add smoke tests for declared outputs when practical.
7. Run the experiment and then `mathgraph check` and `mathgraph orphans`.

## Avoiding Orphan Code

Before adding a nontrivial function, ask which graph node it belongs to:

- simulator code attaches to a `model` or `simulator` node.
- likelihood and posterior code attach to `assumption` nodes unless they are better represented as objectives, estimators, or approximations.
- objective code attaches to `objective` nodes.
- estimator code attaches to `estimator` or `approximation` nodes.
- experiment scripts attach to `experiment` nodes.
- test functions attach to the node whose behavior they validate.

If no node fits, add or update the graph before adding the code. If the function is a private helper, it may be covered by the public symbol attached to the node, but it should still serve that attached implementation.

## Report Checklist

For model-assumption, estimator, or experiment changes, report:

- old and new graph nodes
- new or changed edges
- TeX derivation labels
- code symbols
- test symbols
- generated outputs
- `mathgraph impact` summary
- validation or experiment results
- limitations and assumptions
