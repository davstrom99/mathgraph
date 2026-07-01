"""Initialize mathgraph scaffolding in a repository."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mathgraph_tool.discovery import DiscoveredFile, discover_project_files
from mathgraph_tool.indexing import INDEX_PATH, IndexBuildResult, build_index, serialize_index, serialize_initial_draft


SCAFFOLD_PATHS = [
    Path("mathgraph/graph.yaml"),
    Path("mathgraph/schema.yaml"),
    Path("mathgraph/INIT_CHECKLIST.md"),
    Path("mathgraph/INIT_REPORT.md"),
    Path("mathgraph/INIT_DRAFT.yaml"),
    INDEX_PATH,
    Path("mathgraph/paper/main.tex"),
]

AGENTS_PATH = Path("AGENTS.md")
AGENTS_SECTION_START = "<!-- mathgraph-rules:start -->"
AGENTS_SECTION_END = "<!-- mathgraph-rules:end -->"


@dataclass(frozen=True)
class InitResult:
    planned: list[Path]
    written: list[Path]
    existing: list[Path]
    checklist_count: int
    dry_run: bool = False
    refused: bool = False
    blocked_count: int = 0
    review_mode: str = "source"

    @property
    def ok(self) -> bool:
        return not self.refused and (self.review_mode == "full" or self.blocked_count == 0)


def initialize_mathgraph(
    repo_root: Path,
    *,
    project_id: str | None = None,
    title: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    include_extensions: set[str] | None = None,
    exclude_dirs: set[str] | None = None,
    full_review: bool = False,
    include_generated: bool = False,
) -> InitResult:
    """Create mathgraph scaffolding for a repo."""
    root = repo_root.resolve()
    planned = [root / path for path in SCAFFOLD_PATHS] + [root / AGENTS_PATH]
    existing = [path for path in planned if path.exists()]
    blocking_existing = [root / path for path in SCAFFOLD_PATHS if (root / path).exists()]
    if blocking_existing and not force:
        return InitResult(planned=planned, written=[], existing=blocking_existing, checklist_count=0, dry_run=dry_run, refused=True)

    discovered = discover_project_files(root, include_extensions=include_extensions, exclude_dirs=exclude_dirs)
    index = build_index(
        root,
        files=discovered,
        full_review=full_review,
        write=False,
        include_extensions=include_extensions,
        exclude_dirs=exclude_dirs,
        include_generated=include_generated,
    )
    project_id = project_id or _default_project_id(root)
    title = title or root.name.replace("_", " ").replace("-", " ").title()
    contents = {
        root / "mathgraph/graph.yaml": _graph_yaml(project_id, title),
        root / "mathgraph/schema.yaml": _schema_yaml(),
        root / "mathgraph/INIT_CHECKLIST.md": _checklist(title, discovered, index),
        root / "mathgraph/INIT_REPORT.md": _init_report(title, index),
        root / "mathgraph/INIT_DRAFT.yaml": serialize_initial_draft(index, root),
        root / INDEX_PATH: serialize_index(index),
        root / "mathgraph/paper/main.tex": _main_tex(title),
    }

    if dry_run:
        return InitResult(
            planned=planned,
            written=[],
            existing=existing,
            checklist_count=_checklist_count(index),
            dry_run=True,
            blocked_count=index.blocked,
            review_mode=index.review_mode,
        )

    written: list[Path] = []
    for path, text in contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    agents_path = root / AGENTS_PATH
    if _write_or_append_agents(agents_path):
        written.append(agents_path)
    return InitResult(
        planned=planned,
        written=written,
        existing=existing,
        checklist_count=_checklist_count(index),
        blocked_count=index.blocked,
        review_mode=index.review_mode,
    )


def format_init_result(result: InitResult) -> str:
    if result.refused:
        lines = ["Refusing to initialize because scaffold files already exist:"]
        lines.extend(f"- {_display_path(path)}" for path in result.existing)
        lines.append("")
        lines.append("Use --force to overwrite or inspect the existing files first.")
        return "\n".join(lines)

    action = "Would create" if result.dry_run else "Created"
    lines = [f"{action} mathgraph scaffold:"]
    paths = result.planned if result.dry_run else result.written
    lines.extend(f"- {_display_path(path)}" for path in paths)
    lines.append("")
    lines.append(f"Checklist entries: {result.checklist_count}")
    lines.append(f"Review mode: {result.review_mode}")
    lines.append(f"Blocked index records: {result.blocked_count}")
    lines.append("")
    lines.append("Next steps:")
    lines.append("- If invoked from Codex as `/mathgraph init`, continue the full onboarding workflow now.")
    if result.review_mode == "full":
        lines.append("- Read every file in mathgraph/INIT_CHECKLIST.md completely and fill the review record.")
    else:
        lines.append("- Use mathgraph index dossier first; inspect every authoritative source record and resolve identities with draft-refs/find.")
    if result.blocked_count and result.review_mode == "indexed":
        lines.append("- Initialization is blocked: exclude unsupported files or explicitly invoke `/mathgraph init --full-review`.")
    lines.append("- Write findings to mathgraph/INIT_REPORT.md, then construct the initial graph and TeX references.")
    lines.append("- Run mathgraph check, mathgraph orphans, mathgraph coverage, pytest when available, and mathgraph render.")
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _default_project_id(root: Path) -> str:
    value = root.name.lower().replace(" ", "_").replace("-", "_")
    return "".join(character for character in value if character.isalnum() or character == "_") or "mathgraph_project"


def _graph_yaml(project_id: str, title: str) -> str:
    return f"""project:
  id: {project_id}
  title: {title}
  tex_root: mathgraph/paper/main.tex
  repo_root: .
  code_roots:
    - src
    - experiments
    - tests

nodes: []
edges: []
"""


def _schema_yaml() -> str:
    return """node_kinds:
  - variable
  - assumption
  - objective
  - estimator
  - approximation
  - simulator
  - validation
  - experiment
  - figure
  - dataset
  - test

node_fields:
  uses:
    description: "Optional list of primitive variable node ids or symbols used by a non-variable node."
    invariant: "Every listed variable must resolve to a variable node upstream of the node."
  code:
    description: "Code references; use path plus line for every exact use site and optional symbol references for implementation ownership."
    invariant: "Every node references every source line where its mathematical object is used."
  code.role:
    description: "Optional deterministic role: definition, implementation, caller, test, experiment, or configuration."

project_fields:
  code_roots:
    description: "Optional Python roots/files scanned by mathgraph orphans."
  code_exclude:
    description: "Optional path globs or path parts excluded by mathgraph orphans."
  init_configuration:
    description: "Configure initialization under [tool.mathgraph.init] in pyproject.toml with include, exclude, authoritative, and generated path globs."

edge_kinds:
  - defines
  - assumes
  - depends_on
  - derives
  - implements
  - approximates
  - validates
  - tests
  - generates
  - uses
  - affects
"""


def _main_tex(title: str) -> str:
    return f"""\\documentclass{{article}}

\\title{{{title}}}
\\author{{Mathgraph-Centered Research Workflow}}
\\date{{}}

\\begin{{document}}
\\maketitle

Add declarations under \\texttt{{declarations/}} and put every distinct derivation in its own file under \\texttt{{derivations/}}. Edges sharing one argument may reuse its file and label.

\\end{{document}}
"""


def _agents_md() -> str:
    return f"""{AGENTS_SECTION_START}
## Mathgraph-Centered Repository Rules

This repository is mathgraph-centered.

Before editing code:

1. Work through `mathgraph/INIT_CHECKLIST.md` if the initial graph is still being constructed.
2. For `/mathgraph init`, semantically review authoritative source by default, use `--include-generated` only when requested, and use complete file review only for explicit `--full-review`; never escalate automatically.
3. Do not claim initialization complete while `mathgraph index check` reports blocked, missing, or stale evidence.
4. Identify the relevant mathgraph node or nodes.
5. Update the graph before or together with code changes.
6. Every nontrivial function must attach to a graph node.
7. Every mathematical edge must have a TeX derivation reference.
8. Each variable node contains one variable only and uses its variable-and-domain equation as the title.
9. Every node must reference every source line where its mathematical object is used, using exact `path` plus `line` code entries.
10. Prefer a meaningful one-line equation as a node title; otherwise use a concise description. Equation titles must render to stable local SVG assets.
11. Store every distinct derivation in its own standalone-compilable TeX file. Multiple edges may share one file and label when they use the same argument.
12. After `mathgraph render`, inspect `web/render-report.json` and fix title or derivation fallbacks when local renderers are available.
13. Run `mathgraph check`, `mathgraph orphans`, and relevant tests after changes.
{AGENTS_SECTION_END}
"""


def _write_or_append_agents(path: Path) -> bool:
    section = _agents_md()
    if not path.exists():
        path.write_text(f"# Repository Rules for Codex\n\n{section}", encoding="utf-8")
        return True

    existing = path.read_text(encoding="utf-8")
    if AGENTS_SECTION_START in existing:
        return False

    separator = "\n\n" if existing.endswith("\n") else "\n\n"
    path.write_text(f"{existing}{separator}{section}", encoding="utf-8")
    return True


def _checklist(title: str, files: list[DiscoveredFile], index: IndexBuildResult) -> str:
    records = {
        record["path"]: record
        for record in index.records
        if record.get("record_type") == "file"
    }
    full_review = index.review_mode == "full"
    lines = [
        f"# Mathgraph Initialization Checklist: {title}",
        "",
        "Codex instruction for `/mathgraph init`: this is a work queue, not a passive checklist.",
        "",
        "Complete every item before claiming initialization is done:",
        "",
        f"Review mode: `{index.review_mode}`.",
        "",
        "1. Run `mathgraph index check` and `mathgraph index dossier`.",
        (
            "2. Read every eligible file completely; the index remains the traceability source."
            if full_review
            else "2. Inspect every authoritative source record; use `mathgraph index show <path>` only for needed detail and aggregate non-authoritative families unless this mode explicitly includes them."
        ),
        "3. Mark each authoritative file reviewed only after semantic review; verify each generated family by its aggregate hash record.",
        "4. Summarize cross-file findings in `mathgraph/INIT_REPORT.md`.",
        "5. Create or update `mathgraph/graph.yaml` and `mathgraph/paper/...` so the project has a usable initial graph.",
        "6. Give each variable its own node titled by its variable-and-domain equation; prefer one-line equations for other node titles when meaningful.",
        "7. Use `mathgraph draft-refs <symbol-or-node>` to mechanically generate exact role-classified `path` plus `line` references, then resolve ambiguous identities.",
        "8. Put each distinct derivation in its own standalone TeX file; reuse the same file and label across edges that share the argument.",
        "9. Run `mathgraph check`, `mathgraph orphans`, `mathgraph coverage`, `pytest` when available, and `mathgraph render`.",
        "",
        "Do not edit project source code during initialization unless the user explicitly asks for implementation changes.",
        "Do not claim initialization complete while `mathgraph index check` reports blocked, missing, or stale files.",
        "",
    ]
    if not files:
        lines.append("No eligible project files were found.")
        lines.append("")
        return "\n".join(lines)

    for item in files:
        record = records.get(item.path.as_posix())
        if record is None:
            continue
        details = (
            f"parser={record['parser']}; status={record['status']}; "
            f"lines={record['line_count']}; regions={len(record['regions'])}; symbols={len(record['symbols'])}"
        )
        lines.append(f"- [ ] `{item.path.as_posix()}` - {details}")
    families = [record for record in index.records if record.get("record_type") == "family"]
    if families:
        lines.extend(["", "## Aggregate evidence families", ""])
        for record in families:
            lines.append(
                f"- [ ] `{record['family']}` - {record['evidence_class']}; "
                f"{record['file_count']} files; {record['size_bytes']} bytes; hashes verified"
            )
    lines.extend(["", "Record cross-file identities, graph decisions, use-site coverage, and unresolved questions in `mathgraph/INIT_REPORT.md`.", ""])
    return "\n".join(lines)


def _init_report(title: str, index: IndexBuildResult) -> str:
    families = [record for record in index.records if record.get("record_type") == "family"]
    authoritative_count = sum(
        record.get("evidence_class") == "authoritative"
        for record in index.records
        if record.get("record_type") == "file"
    )
    family_lines = "\n".join(
        f"- `{record['family']}`: {record['file_count']} files, hashes verified ({record['evidence_class']})"
        for record in families
    ) or "- None"
    configured_excludes = list((index.classification or {}).get("exclude", ()))
    exclusion_lines = "\n".join(f"- `{pattern}`" for pattern in configured_excludes) or "- Default generated/cache/rendered/output and binary classifications apply."
    identity_locations: dict[str, int] = {}
    for record in index.records:
        if record.get("record_type") == "file":
            for symbol in record.get("symbols", []):
                identity_locations[symbol["name"]] = identity_locations.get(symbol["name"], 0) + 1
    unresolved = "\n".join(
        f"- `{name}`: {count} candidate definitions"
        for name, count in sorted(identity_locations.items())
        if count > 1
    ) or "- None detected mechanically."
    return f"""# Mathgraph Initialization Report: {title}

This report is filled by Codex during `/mathgraph init`.

- Review mode: `{index.review_mode}`
- Evidence index: `mathgraph/INIT_INDEX.jsonl`
- Initial candidate graph: `mathgraph/INIT_DRAFT.yaml`

## Effective Scope

- Authoritative semantic files: {authoritative_count}
- Semantic exclusions:
{exclusion_lines}
- Aggregate-verified families:
{family_lines}

## File Review Status

- Checklist: `mathgraph/INIT_CHECKLIST.md`
- Reviewed files:
- Unreviewed files:

## Candidate Mathematical Objects

Variables:

Assumptions:

Objectives:

Estimators / algorithms:

Approximations:

Simulators:

Experiments:

Validations / tests:

Datasets / outputs / figures:

## Cross-File Traceability Notes

Record cases where the same mathematical object appears under different names, or where one symbol name is reused for different objects.

## Initial Graph Summary

Nodes:

Edges:

TeX references:

Code references:

Line-level use-site coverage:

Test references:

Output references:

## Commands Run

- `mathgraph check`:
- `mathgraph orphans`:
- `mathgraph coverage`:
- `pytest`:
- `mathgraph render`:

## Unresolved Questions

Mechanically detected candidate identities:
{unresolved}

Add mathematical identity, naming, dependency, or implementation questions that need human confirmation.
"""


def _checklist_count(index: IndexBuildResult) -> int:
    return sum(1 for record in index.records if record.get("record_type") in {"file", "family"})
