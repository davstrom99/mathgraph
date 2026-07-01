# Mathgraph

`mathgraph` is a local CLI for math-centered research projects. It keeps a repository-level graph of variables, assumptions, derivations, code, tests, experiments, and rendered outputs so an agent can change code without losing mathematical traceability.

It includes:

- `mathgraph check` for graph and traceability validation
- `mathgraph impact` for downstream dependency analysis
- `mathgraph orphans` for unattached Python-symbol detection
- `mathgraph render` for a static interactive graph viewer
- `mathgraph init` for bootstrapping an existing repository
- a reusable Codex skill in `codex-skill/mathgraph-centered-research/`

## Install

```bash
git clone https://github.com/davstrom99/mathgraph.git
cd mathgraph
pip install -e ".[dev]"
```

## Quick Start

If the repository already contains `mathgraph/graph.yaml`:

```bash
mathgraph check
mathgraph impact figure.graph_view
mathgraph orphans
mathgraph render
python -m http.server 8000 --bind 127.0.0.1 -d web
```

Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

If you want to initialize a repository that does not yet use mathgraph:

```bash
mathgraph init
mathgraph index build
mathgraph index dossier
```

## Example

This repository includes a small Bayesian example graph with a Gaussian branch and a Student-t alternative branch.

Inspect the graph and render the viewer:

```bash
mathgraph node estimator.beta_map
mathgraph impact model.gaussian_observation --verbose
mathgraph render
python -m http.server 8000 --bind 127.0.0.1 -d web
```

Run the example experiments:

```bash
python experiments/run_gaussian_recovery.py
python experiments/run_student_t_change.py
```

## Codex Skill

This repo ships a Codex skill here:

```text
codex-skill/mathgraph-centered-research/
```

To install it for Codex locally, copy that folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R codex-skill/mathgraph-centered-research ~/.codex/skills/
```

After that, use `mathgraph-centered-research` in Codex when working in repositories that contain `mathgraph/graph.yaml` or when you want graph-first math/code traceability.

## Claude Usage

Claude does not natively consume Codex `SKILL.md` bundles as-is. The practical way to reuse this workflow with Claude is:

1. Copy the guidance from `codex-skill/mathgraph-centered-research/SKILL.md`.
2. Put it into your repository-level `CLAUDE.md` or Claude project instructions.
3. Keep the `references/` notes nearby if you want the fuller workflow details.

In other words, Codex can use the packaged skill directly, while Claude can use the same content as project instructions.

## Core Commands

```bash
mathgraph check
mathgraph node <node-id>
mathgraph impact <node-id>
mathgraph coverage
mathgraph orphans
mathgraph render
mathgraph init
mathgraph index build
mathgraph index dossier
mathgraph draft-refs <symbol-or-node-id>
pytest
```
