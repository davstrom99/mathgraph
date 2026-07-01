"""Deterministic, token-efficient evidence indexing for mathgraph initialization."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import tokenize
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from mathgraph_tool.discovery import (
    CODE_EXTENSIONS,
    DiscoveredFile,
    discover_project_files,
    load_discovery_config,
)


INDEX_PATH = Path("mathgraph/INIT_INDEX.jsonl")
INDEX_SCHEMA_VERSION = 2
PARSER_VERSION = 3
TEXT_DOCUMENT_EXTENSIONS = {
    ".adoc", ".bib", ".csv", ".json", ".md", ".org", ".qmd", ".rmd",
    ".rst", ".toml", ".tsv", ".txt", ".typ", ".yaml", ".yml",
}
BINARY_DOCUMENT_EXTENSIONS = {".docx", ".odt", ".pdf"}
OUTPUT_SUFFIXES = {
    ".csv", ".fig", ".json", ".mat", ".npy", ".npz", ".pdf", ".png",
    ".svg", ".tex", ".tsv", ".txt", ".xlsx",
}
MATH_KEYWORDS = re.compile(
    r"\b(assum|constraint|distribution|estimate|expectation|likelihood|loss|map|"
    r"mean|model|objective|optimi[sz]|posterior|prior|probab|random|sample|"
    r"sigma|variance|unit|validate)\b",
    re.IGNORECASE,
)
IDENTIFIER_RE = re.compile(r"[A-Za-z_]\w*")


@dataclass(frozen=True)
class IndexBuildResult:
    records: list[dict[str, Any]]
    reused: int
    blocked: int
    review_mode: str
    include_extensions: tuple[str, ...] = ()
    exclude_dirs: tuple[str, ...] = ()
    classification: dict[str, tuple[str, ...]] | None = None

    @property
    def passed(self) -> bool:
        return self.review_mode == "full" or self.blocked == 0


@dataclass(frozen=True)
class IndexCheckResult:
    ok: list[str]
    warnings: list[str]
    errors: list[str]

    @property
    def passed(self) -> bool:
        return not self.errors


def build_index(
    repo_root: Path,
    *,
    files: list[DiscoveredFile] | None = None,
    full_review: bool = False,
    write: bool = True,
    index_path: Path = INDEX_PATH,
    include_extensions: set[str] | None = None,
    exclude_dirs: set[str] | None = None,
    include_generated: bool = False,
) -> IndexBuildResult:
    """Build or refresh the initialization evidence index."""
    root = repo_root.resolve()
    discovered = files if files is not None else discover_project_files(
        root, include_extensions=include_extensions, exclude_dirs=exclude_dirs
    )
    destination = root / index_path
    previous = _load_file_records(destination)
    records: list[dict[str, Any]] = []
    reused = 0

    family_members: dict[tuple[str, str], list[dict[str, Any]]] = {}
    mode = "full" if full_review else "include-generated" if include_generated else "source"
    for item in discovered:
        source = root / item.path
        digest = _sha256(source)
        semantic = item.evidence_class == "authoritative" or (
            include_generated and item.evidence_class in {"generated", "cache", "rendered", "output"} and item.category != "binary"
        ) or full_review
        if not semantic:
            key = (item.evidence_class, item.family or item.path.parent.as_posix() or ".")
            family_members.setdefault(key, []).append(
                {"path": item.path.as_posix(), "sha256": digest, "size_bytes": source.stat().st_size}
            )
            continue
        cached = previous.get(item.path.as_posix())
        if (
            cached
            and cached.get("sha256") == digest
            and cached.get("schema_version") == INDEX_SCHEMA_VERSION
            and cached.get("parser_version") == PARSER_VERSION
        ):
            record = cached
            reused += 1
        else:
            record = _index_file(source, item, digest)
        records.append(record)

    for (evidence_class, family), members in sorted(family_members.items()):
        members.sort(key=lambda member: member["path"])
        records.append(_family_record(evidence_class, family, members))

    records.sort(key=lambda record: (record.get("record_type") != "file", record.get("path", record.get("family", ""))))
    config = load_discovery_config(root)
    result = IndexBuildResult(
        records=records,
        reused=reused,
        blocked=sum(record["status"] == "blocked" for record in records),
        review_mode=mode,
        include_extensions=tuple(sorted(include_extensions or set())),
        exclude_dirs=tuple(sorted(exclude_dirs or set())),
        classification={
            "include": config.include,
            "exclude": config.exclude,
            "authoritative": config.authoritative,
            "generated": config.generated,
        },
    )
    if write:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialize_index(result), encoding="utf-8")
    return result


def serialize_index(result: IndexBuildResult) -> str:
    meta = {
        "record_type": "meta",
        "schema_version": INDEX_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "review_mode": result.review_mode,
        "file_count": len(result.records),
        "include_extensions": list(result.include_extensions),
        "exclude_dirs": list(result.exclude_dirs),
        "classification": {key: list(value) for key, value in (result.classification or {}).items()},
    }
    lines = [json.dumps(meta, sort_keys=True)]
    lines.extend(json.dumps(record, sort_keys=True) for record in result.records)
    return "\n".join(lines) + "\n"


def load_index(repo_root: Path, index_path: Path = INDEX_PATH) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = repo_root.resolve() / index_path
    if not path.exists():
        raise ValueError(f"initialization index does not exist: {index_path.as_posix()}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("initialization index is empty")
    try:
        items = [json.loads(line) for line in lines]
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid initialization index JSON: {exc}") from exc
    if items[0].get("record_type") != "meta":
        raise ValueError("initialization index is missing its metadata record")
    return items[0], items[1:]


def check_index(repo_root: Path, index_path: Path = INDEX_PATH) -> IndexCheckResult:
    root = repo_root.resolve()
    ok: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    try:
        meta, records = load_index(root, index_path)
    except ValueError as exc:
        return IndexCheckResult(ok, warnings, [str(exc)])

    if meta.get("schema_version") != INDEX_SCHEMA_VERSION:
        errors.append(f"unsupported index schema version: {meta.get('schema_version')}")
    if meta.get("parser_version") != PARSER_VERSION:
        errors.append(f"stale index parser version: {meta.get('parser_version')}")
    mode = meta.get("review_mode")
    if mode not in {"source", "include-generated", "full"}:
        errors.append(f"invalid index review mode: {mode}")

    includes = set(meta.get("include_extensions") or []) or None
    excludes = set(meta.get("exclude_dirs") or []) or None
    current = build_index(
        root,
        write=False,
        include_extensions=includes,
        exclude_dirs=excludes,
        include_generated=mode == "include-generated",
        full_review=mode == "full",
    )
    expected_by_key = {_record_key(record): record for record in current.records}
    indexed_by_key = {_record_key(record): record for record in records}
    for key in sorted(expected_by_key.keys() - indexed_by_key.keys()):
        errors.append(f"eligible evidence missing from index: {_display_record_key(key)}")
    for key in sorted(indexed_by_key.keys() - expected_by_key.keys()):
        errors.append(f"index contains ineligible or removed evidence: {_display_record_key(key)}")

    blocked: list[str] = []
    for record in records:
        if record.get("record_type") == "family":
            expected = expected_by_key.get(_record_key(record))
            if expected and (
                record.get("sha256") != expected.get("sha256")
                or record.get("file_count") != expected.get("file_count")
            ):
                errors.append(f"indexed evidence family is stale: {record.get('family')}")
            continue
        relative = record.get("path", "")
        source = root / relative
        if not source.exists():
            errors.append(f"indexed file missing: {relative}")
            continue
        if record.get("sha256") != _sha256(source):
            errors.append(f"indexed file is stale: {relative}")
        if record.get("status") == "blocked":
            blocked.append(relative)

    if blocked and mode != "full":
        errors.extend(f"indexed review blocked by unsupported or malformed file: {path}" for path in blocked)
    elif blocked:
        warnings.extend(f"file requires complete semantic review: {path}" for path in blocked)

    if not errors:
        file_count = sum(1 for record in records if record.get("record_type") == "file")
        family_count = sum(1 for record in records if record.get("record_type") == "family")
        ok.append(f"index covers {file_count} semantic files and {family_count} aggregate families with current hashes")
    if not blocked:
        ok.append("all indexed files have supported deterministic parsers")
    return IndexCheckResult(ok, warnings, errors)


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    if record.get("record_type") == "family":
        return "family", f"{record.get('evidence_class')}:{record.get('family')}"
    return "file", str(record.get("path"))


def _display_record_key(key: tuple[str, str]) -> str:
    return key[1]


def format_index_summary(repo_root: Path, limit: int = 100, offset: int = 0) -> str:
    meta, records = load_index(repo_root)
    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
    lines = [
        f"Review mode: {meta['review_mode']}",
        f"Files: {len(records)}",
        "Status: " + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())),
        "",
    ]
    page = records[offset:offset + limit]
    for record in page:
        if record.get("record_type") == "family":
            lines.append(
                f"{record['family']} [{record['evidence_class']}/aggregate] "
                f"files={record['file_count']} bytes={record['size_bytes']} hashes=verified"
            )
        else:
            lines.append(
                f"{record['path']} [{record['language']}/{record['status']}] "
                f"lines={record['line_count']} regions={len(record['regions'])} "
                f"symbols={len(record['symbols'])}"
            )
    remaining = max(0, len(records) - offset - len(page))
    if remaining:
        lines.append(f"... {remaining} more files; rerun with `--offset {offset + len(page)}`.")
    return "\n".join(lines)


def format_index_file(repo_root: Path, relative_path: str, limit: int = 40, offset: int = 0) -> str:
    root = repo_root.resolve()
    _, records = load_index(root)
    normalized = Path(relative_path).as_posix()
    try:
        record = next(item for item in records if item["path"] == normalized)
    except StopIteration as exc:
        raise ValueError(f"file is not present in initialization index: {normalized}") from exc
    source_lines = _safe_source_lines(root / normalized)
    lines = [
        f"File: {normalized}",
        f"Parser: {record['parser']} ({record['status']})",
        f"Hash: {record['sha256']}",
    ]
    if record.get("error"):
        lines.append(f"Error: {record['error']}")
    lines.append("Symbols:")
    lines.extend(
        f"- {symbol['kind']} {symbol['name']} lines {symbol['start_line']}-{symbol['end_line']}"
        for symbol in record["symbols"][offset:offset + limit]
    )
    lines.append("Significant regions:")
    page = record["regions"][offset:offset + limit]
    for region in page:
        snippet = _line_excerpt(source_lines, region["start_line"], region["end_line"])
        lines.append(
            f"- {region['kind']} lines {region['start_line']}-{region['end_line']}: {snippet}"
        )
    omitted = max(0, len(record["regions"]) - offset - len(page))
    if omitted:
        lines.append(f"... {omitted} more regions; rerun with `--offset {offset + len(page)}`.")
    return "\n".join(lines)


def format_index_find(repo_root: Path, identifier: str, limit: int = 100, offset: int = 0) -> str:
    root = repo_root.resolve()
    _, records = load_index(root)
    matches: list[tuple[str, int]] = []
    for record in records:
        for line in record.get("identifiers", {}).get(identifier, []):
            matches.append((record["path"], line))
    matches.sort()
    lines = [f"Identifier: {identifier}", f"Occurrences: {len(matches)}"]
    source_cache: dict[str, list[str]] = {}
    page = matches[offset:offset + limit]
    for path, line in page:
        source_lines = source_cache.setdefault(path, _safe_source_lines(root / path))
        lines.append(f"- {path}:{line}: {_line_excerpt(source_lines, line, line)}")
    remaining = max(0, len(matches) - offset - len(page))
    if remaining:
        lines.append(f"... {remaining} more occurrences; rerun with `--offset {offset + len(page)}`.")
    return "\n".join(lines)


def format_index_dossier(repo_root: Path, limit: int = 200, offset: int = 0) -> str:
    """Emit compact cross-file mathematical evidence without repeated file headers."""
    root = repo_root.resolve()
    meta, records = load_index(root)
    entries: list[tuple[str, str, int, str]] = []
    identity_paths: dict[str, set[str]] = {}
    defined_names = {
        symbol["name"]
        for record in records
        if record.get("record_type") == "file"
        for symbol in record.get("symbols", [])
    }
    for record in records:
        if record.get("record_type") != "file":
            continue
        path = record["path"]
        source = _safe_source_lines(root / path)
        for symbol in record.get("symbols", []):
            section = "Tests" if symbol.get("name", "").startswith("test") else "Definitions and signatures"
            line = int(symbol["start_line"])
            entries.append((section, path, line, _line_excerpt(source, line, line)))
            identity_paths.setdefault(symbol["name"], set()).add(path)
        for region in record.get("regions", []):
            if region.get("kind") == "equation":
                line = int(region["start_line"])
                entries.append(("Equations", path, line, _line_excerpt(source, line, int(region["end_line"]))))
        for default in record.get("defaults", []):
            entries.append(("Configuration defaults", path, int(default["line"]), f"{default['name']}={default.get('value')}"))
        for call in record.get("calls", []):
            if call["name"] in defined_names:
                entries.append(("Call relationships", path, int(call["line"]), f"{call.get('caller') or '<module>'} -> {call['name']}"))
    for name, paths in identity_paths.items():
        if len(paths) > 1:
            entries.append(("Candidate identities", ", ".join(sorted(paths)), 0, name))
    section_order = {
        "Equations": 0,
        "Definitions and signatures": 1,
        "Call relationships": 2,
        "Tests": 3,
        "Configuration defaults": 4,
        "Candidate identities": 5,
    }
    unique = sorted(set(entries), key=lambda item: (section_order[item[0]], item[1], item[2], item[3]))
    page = unique[offset:offset + limit]
    lines = [f"Review mode: {meta['review_mode']}", f"Evidence entries: {len(unique)}"]
    current = None
    for section, path, line, detail in page:
        if section != current:
            lines.extend(["", f"## {section}"])
            current = section
        location = f"{path}:{line}" if line else path
        lines.append(f"- {location}: {detail}")
    remaining = max(0, len(unique) - offset - len(page))
    if remaining:
        lines.append(f"\n... {remaining} more entries; rerun with `--offset {offset + len(page)}`.")
    families = [record for record in records if record.get("record_type") == "family"]
    if families:
        lines.extend(["", "## Aggregate-verified families"])
        lines.extend(
            f"- {record['family']}: {record['file_count']} files, hashes verified ({record['evidence_class']})"
            for record in families
        )
    return "\n".join(lines)


def draft_code_refs(repo_root: Path, target: str) -> dict[str, Any]:
    """Create exhaustive, role-classified exact-line reference YAML data."""
    root = repo_root.resolve()
    identifier = target
    if "." in target and (root / "mathgraph/graph.yaml").exists():
        from mathgraph_tool.loader import load_graph

        graph = load_graph(repo_root=root)
        node = graph.node_by_id.get(target)
        if node is not None:
            identifier = node.symbol or next((ref.symbol for ref in node.code if ref.symbol), "") or target.split(".")[-1]
    _, records = load_index(root)
    refs: dict[tuple[str, int], dict[str, Any]] = {}
    priority = {"definition": 5, "test": 4, "experiment": 3, "configuration": 2, "caller": 1, "implementation": 0}
    for record in records:
        if record.get("record_type") != "file" or record.get("evidence_class") != "authoritative":
            continue
        path = record["path"]
        occurrences = [item for item in record.get("occurrences", []) if item.get("name") == identifier]
        if not occurrences:
            occurrences = [
                {"name": identifier, "line": line, "role": "implementation", "enclosing": None}
                for line in record.get("identifiers", {}).get(identifier, [])
            ]
        for occurrence in occurrences:
            role = _reference_role(path, occurrence.get("role", "implementation"))
            value = {"path": path, "line": int(occurrence["line"]), "role": role}
            if role == "definition":
                value["symbol"] = identifier
            key = (path, value["line"])
            if key not in refs or priority[role] > priority[refs[key]["role"]]:
                refs[key] = value
    return {"target": target, "identifier": identifier, "code": [refs[key] for key in sorted(refs)]}


def format_draft_refs(repo_root: Path, target: str) -> str:
    return yaml.safe_dump(draft_code_refs(repo_root, target), sort_keys=False, allow_unicode=True)


def serialize_initial_draft(result: IndexBuildResult, repo_root: Path | None = None) -> str:
    """Generate deterministic graph candidates for later semantic resolution."""
    symbols: list[dict[str, Any]] = []
    tex_labels: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    equations: list[dict[str, Any]] = []
    identities: dict[str, list[str]] = {}
    for record in result.records:
        if record.get("record_type") != "file":
            continue
        path = record["path"]
        for symbol in record.get("symbols", []):
            candidate = {"name": symbol["name"], "kind": symbol["kind"], "path": path, "line": symbol["start_line"]}
            symbols.append(candidate)
            identities.setdefault(symbol["name"], []).append(f"{path}:{symbol['start_line']}")
            if record.get("language") == "tex" and symbol.get("kind") == "label":
                tex_labels.append(candidate)
        for call in record.get("calls", []):
            relationships.append({"caller": call.get("caller"), "callee": call["name"], "path": path, "line": call["line"]})
        equations.extend(
            {"path": path, "start_line": region["start_line"], "end_line": region["end_line"]}
            for region in record.get("regions", [])
            if region.get("kind") == "equation"
        )
    provenance = _existing_provenance_candidates(repo_root, result.records)
    payload = {
        "review_mode": result.review_mode,
        "generated_by": "mathgraph init",
        "candidates": {
            "symbols": symbols,
            "tex_labels": tex_labels,
            "equations": equations,
            "calls": relationships,
            "provenance": provenance,
        },
        "unresolved_identities": [
            {"name": name, "occurrences": locations}
            for name, locations in sorted(identities.items())
            if len(locations) > 1
        ],
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def _existing_provenance_candidates(repo_root: Path | None, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if repo_root is None:
        return candidates
    root = repo_root.resolve()
    paths = [root / "mathgraph/graph.yaml", root / "graphify-out/graph.json"]
    indexed_hashes = {
        member["path"]: member["sha256"]
        for record in records
        if record.get("record_type") == "family"
        for member in record.get("members", [])
    }
    for path in paths:
        if not path.exists():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        relative = path.relative_to(root).as_posix()
        candidates.append(
            {
                "path": relative,
                "sha256": indexed_hashes.get(relative) or _sha256(path),
                "nodes": len(data.get("nodes", [])) if isinstance(data, dict) else 0,
                "edges": len(data.get("edges", [])) if isinstance(data, dict) else 0,
            }
        )
    return candidates


def _reference_role(path: str, indexed_role: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("tests/") or "/tests/" in f"/{normalized}":
        return "test"
    if normalized.startswith("experiments/") or "/experiments/" in f"/{normalized}":
        return "experiment"
    if Path(normalized).suffix.lower() in {".toml", ".yaml", ".yml", ".json"}:
        return "configuration"
    return indexed_role if indexed_role in {"definition", "caller"} else "implementation"


def format_index_check(result: IndexCheckResult) -> str:
    lines = [f"OK: {item}." for item in result.ok]
    if result.warnings:
        lines.extend(["", "Warnings:", *(f"- {item}" for item in result.warnings)])
    if result.errors:
        lines.extend(["", "Errors:", *(f"- {item}" for item in result.errors)])
    return "\n".join(lines)


def indexed_line_exists(records: Iterable[dict[str, Any]], path: str, line: int) -> bool:
    normalized = Path(path).as_posix()
    for record in records:
        if record.get("path") == normalized:
            return 1 <= line <= int(record.get("line_count", 0))
    return False


def _index_file(source: Path, item: DiscoveredFile, digest: str) -> dict[str, Any]:
    suffix = source.suffix.lower()
    if suffix == ".py":
        parser, language, extractor = "python-ast-tokenize-v1", "python", _extract_python
    elif suffix == ".m":
        parser, language, extractor = "matlab-lexer-v1", "matlab", _extract_matlab
    elif suffix == ".tex":
        parser, language, extractor = "tex-scanner-v1", "tex", _extract_tex
    elif suffix == ".json":
        parser, language, extractor = "json-stdlib-v1", "json", _extract_json
    elif suffix == ".toml":
        parser, language, extractor = "tomllib-v1", "toml", _extract_toml
    elif suffix in TEXT_DOCUMENT_EXTENSIONS:
        parser, language, extractor = "generic-text-v1", suffix.lstrip("."), _extract_generic
    elif suffix in BINARY_DOCUMENT_EXTENSIONS or suffix in CODE_EXTENSIONS:
        return _blocked_record(source, item, digest, suffix.lstrip(".") or "unknown", "no supported deterministic parser")
    else:
        return _blocked_record(source, item, digest, suffix.lstrip(".") or "unknown", "unsupported file type")

    try:
        text = source.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as exc:
        return _blocked_record(source, item, digest, language, f"could not read UTF-8 text: {exc}")
    try:
        payload = extractor(text)
    except (SyntaxError, tokenize.TokenError, ValueError) as exc:
        return _blocked_record(source, item, digest, language, str(exc), line_count=len(text.splitlines()))
    return {
        "record_type": "file",
        "schema_version": INDEX_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "path": item.path.as_posix(),
        "category": item.category,
        "evidence_class": item.evidence_class,
        "language": language,
        "parser": parser,
        "status": "ok",
        "error": None,
        "sha256": digest,
        "size_bytes": source.stat().st_size,
        "line_count": len(text.splitlines()),
        **payload,
    }


def _blocked_record(
    source: Path,
    item: DiscoveredFile,
    digest: str,
    language: str,
    error: str,
    *,
    line_count: int = 0,
) -> dict[str, Any]:
    return {
        "record_type": "file",
        "schema_version": INDEX_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "path": item.path.as_posix(),
        "category": item.category,
        "evidence_class": item.evidence_class,
        "language": language,
        "parser": "unsupported",
        "status": "blocked",
        "error": error,
        "sha256": digest,
        "size_bytes": source.stat().st_size,
        "line_count": line_count,
        "symbols": [],
        "identifiers": {},
        "regions": [],
        "tests": [],
        "assertions": [],
        "defaults": [],
        "outputs": [],
        "occurrences": [],
        "calls": [],
    }


def _family_record(evidence_class: str, family: str, members: list[dict[str, Any]]) -> dict[str, Any]:
    digest = hashlib.sha256()
    for member in members:
        digest.update(member["path"].encode("utf-8"))
        digest.update(member["sha256"].encode("ascii"))
    return {
        "record_type": "family",
        "schema_version": INDEX_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "family": family,
        "evidence_class": evidence_class,
        "status": "aggregate",
        "file_count": len(members),
        "size_bytes": sum(member["size_bytes"] for member in members),
        "sha256": digest.hexdigest(),
        "members": members,
    }


def _extract_python(text: str) -> dict[str, Any]:
    tree = ast.parse(text)
    lines = text.splitlines()
    symbols: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    assertions: list[int] = []
    defaults: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            symbols.append(_symbol(node.name, kind, node.lineno, end))
            regions.append(_region("signature", node.lineno, node.lineno))
            if node.name.startswith("test"):
                tests.append(_symbol(node.name, kind, node.lineno, end))
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                regions.append(_region("docstring", body[0].lineno, getattr(body[0], "end_lineno", body[0].lineno)))
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                positional = list(node.args.posonlyargs) + list(node.args.args)
                for argument, default in zip(positional[-len(node.args.defaults):], node.args.defaults):
                    defaults.append({"name": argument.arg, "line": default.lineno, "value": ast.get_source_segment(text, default)})
                    regions.append(_region("default", default.lineno, getattr(default, "end_lineno", default.lineno)))
                for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                    if default is not None:
                        defaults.append({"name": argument.arg, "line": default.lineno, "value": ast.get_source_segment(text, default)})
                        regions.append(_region("default", default.lineno, getattr(default, "end_lineno", default.lineno)))
        elif isinstance(node, ast.Assert):
            assertions.append(node.lineno)
            regions.append(_region("assertion", node.lineno, getattr(node, "end_lineno", node.lineno)))
        elif isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
            regions.append(_region("assignment", node.lineno, getattr(node, "end_lineno", node.lineno)))
        elif isinstance(node, ast.If | ast.While):
            regions.append(_region("condition", node.lineno, getattr(node.test, "end_lineno", node.lineno)))
        elif isinstance(node, ast.Call):
            name = _python_call_name(node.func)
            if MATH_KEYWORDS.search(name) or re.search(r"(minimize|normal|random|sample|solve|fit|predict|logpdf)", name, re.I):
                regions.append(_region("mathematical-call", node.lineno, getattr(node, "end_lineno", node.lineno)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if Path(node.value).suffix.lower() in OUTPUT_SUFFIXES:
                outputs.append({"path": node.value, "line": node.lineno})

    comments: list[tuple[int, str]] = []
    identifiers: dict[str, set[int]] = {}
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.NAME:
            identifiers.setdefault(token.string, set()).add(token.start[0])
        elif token.type == tokenize.COMMENT:
            comments.append((token.start[0], token.string))
    for line, comment in comments:
        if MATH_KEYWORDS.search(comment) or any(marker in comment for marker in ("=", "~", "->", "<=")):
            regions.append(_region("mathematical-comment", line, line))
    occurrences, calls = _python_occurrences(tree)
    return _payload(symbols, identifiers, regions, tests, assertions, defaults, outputs, occurrences, calls)


def _python_occurrences(tree: ast.AST) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    occurrences: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            occurrences.append({"name": node.name, "line": node.lineno, "role": "definition", "enclosing": self.enclosing})
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            occurrences.append({"name": node.name, "line": node.lineno, "role": "definition", "enclosing": self.enclosing})
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_Name(self, node: ast.Name) -> None:
            role = "definition" if isinstance(node.ctx, (ast.Store, ast.Param)) else "implementation"
            occurrences.append({"name": node.id, "line": node.lineno, "role": role, "enclosing": self.enclosing})

        def visit_Call(self, node: ast.Call) -> None:
            name = _python_call_name(node.func).split(".")[-1]
            if name:
                calls.append({"name": name, "line": node.lineno, "caller": self.enclosing})
                occurrences.append({"name": name, "line": node.lineno, "role": "caller", "enclosing": self.enclosing})
            self.generic_visit(node)

        @property
        def enclosing(self) -> str | None:
            return ".".join(self.scope) if self.scope else None

    Visitor().visit(tree)
    unique = {(item["name"], item["line"], item["role"], item["enclosing"]): item for item in occurrences}
    return sorted(unique.values(), key=lambda item: (item["line"], item["name"], item["role"])), calls


def _extract_matlab(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if text.count("%{") != text.count("%}"):
        raise ValueError("unbalanced MATLAB block comment")
    symbols: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    assertions: list[int] = []
    defaults: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    identifiers: dict[str, set[int]] = {}
    function_re = re.compile(
        r"^\s*function\s+(?:\[[^]]*\]|\w+)\s*=\s*(\w+)"
        r"|^\s*function\s+(\w+)(?:\s*\(|\s*$)"
    )
    class_re = re.compile(r"^\s*classdef(?:\s*\([^)]*\))?\s+(\w+)")
    assignment_re = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+?);?\s*$")
    in_block_comment = False
    default_window = 0

    for number, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("%{"):
            in_block_comment = True
        if not in_block_comment:
            code = _matlab_code_part(raw)
            for identifier in IDENTIFIER_RE.findall(code):
                identifiers.setdefault(identifier, set()).add(number)
            match = function_re.search(code)
            if match:
                name = match.group(1) or match.group(2)
                symbol = _symbol(name, "function", number, number)
                symbols.append(symbol)
                regions.append(_region("signature", number, number))
                if name.lower().startswith("test"):
                    tests.append(symbol)
            class_match = class_re.search(code)
            if class_match:
                symbols.append(_symbol(class_match.group(1), "class", number, number))
                regions.append(_region("signature", number, number))
            assignment = assignment_re.search(code)
            if assignment:
                regions.append(_region("assignment", number, number))
                if default_window > 0:
                    defaults.append({"name": assignment.group(1), "line": number, "value": assignment.group(2).rstrip(";")})
            if re.search(r"\b(if|elseif|while)\b", code):
                regions.append(_region("condition", number, number))
            if re.search(r"\b(nargin|isempty|exist\s*\()", code):
                default_window = 5
            if re.search(r"\bassert\s*\(", code):
                assertions.append(number)
                regions.append(_region("assertion", number, number))
            if re.search(r"\b(fmin|fit|log|mean|norm|optim|rand|sample|solve|std|var)\w*\s*\(", code, re.I):
                regions.append(_region("mathematical-call", number, number))
            for value in re.findall(r"['\"]([^'\"]+)['\"]", code):
                if Path(value).suffix.lower() in OUTPUT_SUFFIXES:
                    outputs.append({"path": value, "line": number})
            default_window = max(0, default_window - 1)
        if stripped.startswith("%%") or (stripped.startswith("%") and (MATH_KEYWORDS.search(stripped) or "=" in stripped)):
            regions.append(_region("mathematical-comment", number, number))
        if stripped.endswith("%}"):
            in_block_comment = False
    return _payload(symbols, identifiers, regions, tests, assertions, defaults, outputs)


def _extract_tex(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    begin_re = re.compile(r"\\begin\{([^}]+)\}")
    end_re = re.compile(r"\\end\{([^}]+)\}")
    math_envs = {"align", "align*", "equation", "equation*", "gather", "gather*", "multline", "multline*"}
    stack: list[tuple[str, int]] = []
    symbols: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    identifiers: dict[str, set[int]] = {}

    for number, line in enumerate(lines, start=1):
        for identifier in re.findall(r"\\([A-Za-z]+)|\b([A-Za-z]\w*)\b", line):
            value = identifier[0] or identifier[1]
            identifiers.setdefault(value, set()).add(number)
        for label in re.findall(r"\\label\{([^}]+)\}", line):
            symbols.append(_symbol(label, "label", number, number))
        if re.search(r"\\(newcommand|renewcommand|DeclareMathOperator)\b", line):
            regions.append(_region("definition", number, number))
        if re.search(r"\\(part|chapter|section|subsection|paragraph)\{", line):
            regions.append(_region("heading", number, number))
        if re.search(r"\\(input|include)\{", line):
            regions.append(_region("include", number, number))
        if re.search(r"\\(ref|eqref|cite)\{", line):
            regions.append(_region("reference", number, number))
        if MATH_KEYWORDS.search(line):
            regions.append(_region("mathematical-prose", number, number))
        for env in begin_re.findall(line):
            stack.append((env, number))
        for env in end_re.findall(line):
            if not stack or stack[-1][0] != env:
                raise ValueError(f"unbalanced TeX environment {env} at line {number}")
            opened, start = stack.pop()
            if opened in math_envs:
                regions.append(_region("equation", start, number))
        if "\\[" in line or "\\(" in line or "$" in line:
            regions.append(_region("inline-math", number, number))
    if stack:
        env, line = stack[-1]
        raise ValueError(f"unclosed TeX environment {env} from line {line}")
    return _payload(symbols, identifiers, regions, [], [], [], [])


def _extract_generic(text: str) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    identifiers: dict[str, set[int]] = {}
    outputs: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for identifier in IDENTIFIER_RE.findall(line):
            identifiers.setdefault(identifier, set()).add(number)
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+", stripped) or re.match(r"^\[[^]]+\]\s*$", stripped):
            regions.append(_region("heading", number, number))
        if MATH_KEYWORDS.search(line) or any(marker in line for marker in ("\\[", "$$", " := ", " ~ ")):
            regions.append(_region("mathematical-text", number, number))
        for value in re.findall(r"['\"]([^'\"]+)['\"]", line):
            if Path(value).suffix.lower() in OUTPUT_SUFFIXES:
                outputs.append({"path": value, "line": number})
    return _payload(symbols, identifiers, regions, [], [], [], outputs)


def _extract_json(text: str) -> dict[str, Any]:
    json.loads(text)
    return _extract_generic(text)


def _extract_toml(text: str) -> dict[str, Any]:
    tomllib.loads(text)
    return _extract_generic(text)


def _payload(symbols, identifiers, regions, tests, assertions, defaults, outputs, occurrences=None, calls=None) -> dict[str, Any]:
    deduped_regions = {
        (region["kind"], region["start_line"], region["end_line"]): region
        for region in regions
    }
    return {
        "symbols": sorted(symbols, key=lambda item: (item["start_line"], item["name"])),
        "identifiers": {name: sorted(lines) for name, lines in sorted(identifiers.items())},
        "regions": sorted(deduped_regions.values(), key=lambda item: (item["start_line"], item["end_line"], item["kind"])),
        "tests": sorted(tests, key=lambda item: (item["start_line"], item["name"])),
        "assertions": sorted(set(assertions)),
        "defaults": sorted(defaults, key=lambda item: (item["line"], item["name"])),
        "outputs": sorted(outputs, key=lambda item: (item["line"], item["path"])),
        "occurrences": occurrences or [],
        "calls": calls or [],
    }


def _symbol(name: str, kind: str, start: int, end: int) -> dict[str, Any]:
    return {"name": name, "kind": kind, "start_line": start, "end_line": end}


def _region(kind: str, start: int, end: int) -> dict[str, Any]:
    return {"kind": kind, "start_line": start, "end_line": end}


def _python_call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_python_call_name(node.value)}.{node.attr}".strip(".")
    return ""


def _matlab_code_part(line: str) -> str:
    result: list[str] = []
    in_string = False
    quote = ""
    index = 0
    while index < len(line):
        character = line[index]
        if in_string:
            result.append(character)
            if character == quote:
                if index + 1 < len(line) and line[index + 1] == quote:
                    result.append(line[index + 1])
                    index += 1
                else:
                    in_string = False
        elif character == "'" and _is_matlab_transpose(result):
            result.append(character)
        elif character in {"'", '"'}:
            in_string = True
            quote = character
            result.append(character)
        elif character == "%":
            break
        else:
            result.append(character)
        index += 1
    if in_string:
        raise ValueError("unterminated MATLAB string")
    return "".join(result)


def _is_matlab_transpose(characters: list[str]) -> bool:
    previous = next((character for character in reversed(characters) if not character.isspace()), "")
    return bool(previous and (previous.isalnum() or previous in "_)]}"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_file_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        _, records = load_index(path.parent.parent, path.relative_to(path.parent.parent))
    except (ValueError, OSError):
        return {}
    return {
        record["path"]: record
        for record in records
        if record.get("record_type") == "file" and record.get("path")
    }


def _safe_source_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8-sig").splitlines()
    except (UnicodeDecodeError, OSError):
        return []


def _line_excerpt(lines: list[str], start: int, end: int, limit: int = 220) -> str:
    if not lines or start < 1:
        return "<source unavailable>"
    selected = " ".join(line.strip() for line in lines[start - 1:min(end, len(lines))])
    selected = re.sub(r"[\x00-\x1f\x7f]", " ", selected)
    selected = re.sub(r"\s+", " ", selected)
    return selected if len(selected) <= limit else selected[: limit - 3] + "..."
