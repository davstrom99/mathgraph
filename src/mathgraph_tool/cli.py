"""Command-line interface for mathgraph."""

from __future__ import annotations

import argparse
import json
import sys

from mathgraph_tool.analysis import (
    format_coverage_report,
    format_impact_report,
    format_node_card,
)
from mathgraph_tool.checks import format_check_result, run_checks
from mathgraph_tool.init import format_init_result, initialize_mathgraph
from mathgraph_tool.indexing import (
    build_index,
    check_index,
    format_draft_refs,
    format_index_check,
    format_index_dossier,
    format_index_file,
    format_index_find,
    format_index_summary,
)
from mathgraph_tool.loader import find_repo_root
from mathgraph_tool.orphans import find_orphans, format_orphan_report
from mathgraph_tool.render import render_static_site


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mathgraph")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize mathgraph scaffolding")
    init_parser.add_argument("--project-id", help="project id for the initial graph")
    init_parser.add_argument("--title", help="project title for the initial graph")
    init_parser.add_argument("--force", action="store_true", help="overwrite existing scaffold files")
    init_parser.add_argument("--dry-run", action="store_true", help="show planned scaffold files without writing")
    init_parser.add_argument("--include-extension", action="append", help="extension set to include instead of defaults; may be repeated")
    init_parser.add_argument("--exclude-dir", action="append", help="directory name to exclude; may be repeated")
    init_parser.add_argument(
        "--include-generated",
        action="store_true",
        help="include textual generated/cache/output evidence in indexed semantic review",
    )
    init_parser.add_argument(
        "--full-review",
        action="store_true",
        help="require complete semantic reading of every eligible file instead of indexed-region review",
    )

    index_parser = subparsers.add_parser("index", help="build and query the initialization evidence index")
    index_subparsers = index_parser.add_subparsers(dest="index_command", required=True)
    index_build = index_subparsers.add_parser("build", help="build or refresh mathgraph/INIT_INDEX.jsonl")
    index_build.add_argument("--full-review", action="store_true", help="record full-review mode in the index")
    index_build.add_argument("--include-generated", action="store_true", help="include textual generated evidence in semantic review")
    index_summary = index_subparsers.add_parser("summary", help="show bounded index coverage and parser status")
    index_summary.add_argument("--limit", type=int, default=100, help="maximum file records to print")
    index_summary.add_argument("--offset", type=int, default=0, help="file record offset for pagination")
    index_show = index_subparsers.add_parser("show", help="show significant regions for one indexed file")
    index_show.add_argument("path", help="repository-relative indexed file path")
    index_show.add_argument("--limit", type=int, default=40, help="maximum symbols and regions to print")
    index_show.add_argument("--offset", type=int, default=0, help="symbol and region offset for pagination")
    index_find = index_subparsers.add_parser("find", help="find exact indexed identifier occurrences")
    index_find.add_argument("identifier", help="case-sensitive identifier to find")
    index_find.add_argument("--limit", type=int, default=100, help="maximum occurrences to print")
    index_find.add_argument("--offset", type=int, default=0, help="occurrence offset for pagination")
    index_subparsers.add_parser("check", help="validate index coverage, parsers, and source hashes")
    index_dossier = index_subparsers.add_parser("dossier", help="show compact cross-file mathematical evidence")
    index_dossier.add_argument("--limit", type=int, default=200, help="maximum evidence entries to print")
    index_dossier.add_argument("--offset", type=int, default=0, help="evidence entry offset for pagination")

    refs_parser = subparsers.add_parser("draft-refs", help="emit exhaustive role-classified YAML code references")
    refs_parser.add_argument("target", help="indexed symbol or existing graph node id")
    refs_parser.add_argument("--output", help="write YAML to this repository-relative path instead of stdout")

    check_parser = subparsers.add_parser("check", help="validate the mathgraph YAML file")
    check_parser.add_argument(
        "--graph",
        default="mathgraph/graph.yaml",
        help="path to the graph YAML file, relative to the repository root",
    )

    node_parser = subparsers.add_parser("node", help="print a graph node card")
    node_parser.add_argument("node_id", help="node id to inspect")

    impact_parser = subparsers.add_parser("impact", help="show downstream impact from a node")
    impact_parser.add_argument("node_id", help="node id to analyze")
    impact_parser.add_argument("--verbose", action="store_true", help="include edge paths and descriptions")

    subparsers.add_parser("coverage", help="summarize graph coverage")
    subparsers.add_parser("render", help="generate the static graph webpage in web/")

    orphans_parser = subparsers.add_parser("orphans", help="report Python symbols not attached to graph nodes")
    orphans_parser.add_argument("--root", action="append", dest="roots", help="Python root path to scan; may be repeated")
    orphans_parser.add_argument("--exclude", action="append", dest="excludes", help="path glob or path part to exclude; may be repeated")
    orphans_parser.add_argument("--include-private", action="store_true", help="include symbols whose names start with underscore")
    orphans_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "include_generated", False) and getattr(args, "full_review", False):
        parser.error("--include-generated and --full-review are mutually exclusive")

    if args.command == "init":
        result = initialize_mathgraph(
            find_repo_root(),
            project_id=args.project_id,
            title=args.title,
            force=args.force,
            dry_run=args.dry_run,
            include_extensions=set(args.include_extension) if args.include_extension else None,
            exclude_dirs=set(args.exclude_dir) if args.exclude_dir else None,
            full_review=args.full_review,
            include_generated=args.include_generated,
        )
        print(format_init_result(result))
        return 0 if result.ok else 1

    if args.command == "check":
        result = run_checks(args.graph)
        print(format_check_result(result))
        return 0 if result.passed else 1

    if args.command == "index":
        root = find_repo_root()
        try:
            if args.index_command == "build":
                result = build_index(root, full_review=args.full_review, include_generated=args.include_generated)
                semantic_files = sum(1 for record in result.records if record.get("record_type") == "file")
                families = sum(1 for record in result.records if record.get("record_type") == "family")
                print(
                    f"Indexed {semantic_files} semantic files and {families} aggregate families; "
                    f"reused {result.reused}; blocked {result.blocked}; review mode {result.review_mode}."
                )
                return 0 if result.passed else 1
            if args.index_command == "summary":
                print(format_index_summary(root, limit=max(1, args.limit), offset=max(0, args.offset)))
                return 0
            if args.index_command == "show":
                print(format_index_file(root, args.path, limit=max(1, args.limit), offset=max(0, args.offset)))
                return 0
            if args.index_command == "find":
                print(format_index_find(root, args.identifier, limit=max(1, args.limit), offset=max(0, args.offset)))
                return 0
            if args.index_command == "check":
                result = check_index(root)
                print(format_index_check(result))
                return 0 if result.passed else 1
            if args.index_command == "dossier":
                print(format_index_dossier(root, limit=max(1, args.limit), offset=max(0, args.offset)))
                return 0
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    try:
        if args.command == "draft-refs":
            root = find_repo_root()
            output = format_draft_refs(root, args.target)
            if args.output:
                destination = root / args.output
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(output, encoding="utf-8")
                print(f"Wrote {destination.relative_to(root).as_posix()}")
            else:
                print(output, end="")
            return 0
        if args.command == "node":
            print(format_node_card(args.node_id))
            return 0
        if args.command == "impact":
            print(format_impact_report(args.node_id, verbose=args.verbose))
            return 0
        if args.command == "coverage":
            print(format_coverage_report())
            return 0
        if args.command == "render":
            paths = render_static_site()
            print("Generated static graph webpage:")
            for path in paths:
                print(f"- {path}")
            report_path = next((path for path in paths if path.name == "render-report.json"), None)
            if report_path and report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                titles = report.get("node_titles", [])
                derivations = [item for item in report.get("tex", []) if item.get("kind") == "derivation"]
                title_fallbacks = sum(item.get("status") != "rendered" for item in titles)
                derivation_fallbacks = sum(item.get("status") == "browser-fallback" for item in derivations)
                print("")
                print(
                    f"Math rendering: {len(titles) - title_fallbacks}/{len(titles)} node titles rendered locally; "
                    f"{len(derivations) - derivation_fallbacks}/{len(derivations)} derivations compiled locally."
                )
                if title_fallbacks or derivation_fallbacks:
                    print("Warning: inspect render-report.json; some math assets require fallback rendering.")
            print("")
            print("Serve it with:")
            print("  python -m http.server 8000 --bind 127.0.0.1 -d web")
            print("")
            print("Then open:")
            print("  http://127.0.0.1:8000/")
            print("")
            print("The server command stays running; press Ctrl+C in that terminal to stop it.")
            return 0
        if args.command == "orphans":
            report = find_orphans(
                roots=args.roots,
                excludes=args.excludes,
                include_private=args.include_private,
            )
            print(format_orphan_report(report, as_json=args.json))
            return 0 if report.passed else 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
