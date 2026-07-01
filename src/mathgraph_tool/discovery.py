"""Repository file discovery for mathgraph initialization."""

from __future__ import annotations

import os
import fnmatch
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from dataclasses import dataclass
from pathlib import Path


CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".cxx",
    ".f",
    ".f90",
    ".f95",
    ".go",
    ".h",
    ".hpp",
    ".ipynb",
    ".java",
    ".jl",
    ".js",
    ".jsx",
    ".kt",
    ".lua",
    ".m",
    ".nim",
    ".php",
    ".ps1",
    ".py",
    ".r",
    ".R",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".sql",
    ".stan",
    ".swift",
    ".ts",
    ".tsx",
}

DOCUMENT_EXTENSIONS = {
    ".adoc",
    ".bib",
    ".csv",
    ".docx",
    ".json",
    ".md",
    ".odt",
    ".org",
    ".pdf",
    ".qmd",
    ".rmd",
    ".rst",
    ".tex",
    ".toml",
    ".tsv",
    ".txt",
    ".typ",
    ".yaml",
    ".yml",
}

BINARY_EXTENSIONS = {".docx", ".gif", ".jpeg", ".jpg", ".mat", ".npy", ".npz", ".odt", ".pdf", ".png", ".xlsx"}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "env",
    "mathgraph",
    "node_modules",
    "target",
    "venv",
}

DEFAULT_CLASSIFICATION_PATTERNS = {
    "cache": ("graphify-out/cache/**", "**/__pycache__/**"),
    "rendered": ("web/**",),
    "output": ("results/**",),
    "generated": ("graphify-out/**", "build/**", "dist/**", "**/*.egg-info/**"),
    "vendored": ("vendor/**", "third_party/**"),
}

EXCLUDED_FILE_SUFFIXES = {
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".fls",
    ".fdb_latexmk",
    ".idx",
    ".ilg",
    ".ind",
    ".lof",
    ".log",
    ".lot",
    ".out",
    ".synctex.gz",
    ".toc",
}

EXCLUDED_FILE_NAMES = {"AGENTS.md"}


@dataclass(frozen=True)
class DiscoveredFile:
    path: Path
    category: str
    evidence_class: str = "authoritative"
    family: str | None = None


@dataclass(frozen=True)
class DiscoveryConfig:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    authoritative: tuple[str, ...] = ()
    generated: tuple[str, ...] = ()


def load_discovery_config(root: Path) -> DiscoveryConfig:
    """Load optional source-classification rules from pyproject.toml."""
    path = root.resolve() / "pyproject.toml"
    if not path.exists():
        return DiscoveryConfig()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return DiscoveryConfig()
    values = data.get("tool", {}).get("mathgraph", {}).get("init", {})
    if not isinstance(values, dict):
        return DiscoveryConfig()
    return DiscoveryConfig(
        include=_string_tuple(values.get("include")),
        exclude=_string_tuple(values.get("exclude")),
        authoritative=_string_tuple(values.get("authoritative")),
        generated=_string_tuple(values.get("generated")),
    )


def discover_project_files(
    root: Path,
    *,
    include_extensions: set[str] | None = None,
    exclude_dirs: set[str] | None = None,
) -> list[DiscoveredFile]:
    """Return eligible files for Codex-led graph initialization."""
    root = root.resolve()
    includes = {_normalize_extension(value) for value in include_extensions} if include_extensions else (CODE_EXTENSIONS | DOCUMENT_EXTENSIONS)
    excluded = EXCLUDED_DIR_NAMES
    config = load_discovery_config(root)
    explicit_excludes = tuple(config.exclude) + tuple(f"**/{name}/**" for name in sorted(exclude_dirs or set()))
    discovered: list[DiscoveredFile] = []

    for path in _walk_files(root, excluded):
        relative = path.relative_to(root)
        if _is_excluded(relative, excluded):
            continue
        suffix = _normalized_suffix(path)
        evidence_class, family = _classify(relative, config, explicit_excludes)
        explicitly_included = _matches_any(relative.as_posix(), config.include)
        if suffix in BINARY_EXTENSIONS and not explicitly_included and not _matches_any(relative.as_posix(), config.authoritative):
            evidence_class, family = "binary", "binary artifacts"
        if suffix not in includes and evidence_class == "authoritative" and not explicitly_included:
            continue
        category = "code" if suffix in CODE_EXTENSIONS else "document"
        if suffix not in includes:
            category = "binary"
        discovered.append(DiscoveredFile(relative, category, evidence_class, family))
    return discovered


def _walk_files(root: Path, excluded_dirs: set[str]) -> list[Path]:
    files: list[Path] = []
    for current, dirs, filenames in os.walk(root, topdown=True, followlinks=False, onerror=lambda _: None):
        dirs[:] = sorted(directory for directory in dirs if directory not in excluded_dirs)
        current_path = Path(current)
        for filename in sorted(filenames):
            files.append(current_path / filename)
    return files


def _is_excluded(relative: Path, excluded_dirs: set[str]) -> bool:
    if any(part in excluded_dirs for part in relative.parts[:-1]):
        return True
    name = relative.name
    if name in EXCLUDED_FILE_NAMES:
        return True
    if name.startswith(".") and name not in {".env.example"}:
        return True
    return any(name.endswith(suffix) for suffix in EXCLUDED_FILE_SUFFIXES)


def _normalized_suffix(path: Path) -> str:
    name = path.name
    for suffix in EXCLUDED_FILE_SUFFIXES:
        if name.endswith(suffix):
            return suffix
    return path.suffix


def _normalize_extension(value: str) -> str:
    return value if value.startswith(".") else f".{value}"


def _classify(relative: Path, config: DiscoveryConfig, explicit_excludes: tuple[str, ...]) -> tuple[str, str | None]:
    value = relative.as_posix()
    if _matches_any(value, config.authoritative) or _matches_any(value, config.include):
        return "authoritative", None
    if _matches_any(value, explicit_excludes):
        pattern = next(pattern for pattern in explicit_excludes if _matches(value, pattern))
        return "excluded", _family_name(pattern, value)
    if _matches_any(value, config.generated):
        pattern = next(pattern for pattern in config.generated if _matches(value, pattern))
        return "generated", _family_name(pattern, value)
    for evidence_class, patterns in DEFAULT_CLASSIFICATION_PATTERNS.items():
        for pattern in patterns:
            if _matches(value, pattern):
                return evidence_class, _family_name(pattern, value)
    return "authoritative", None


def _matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(_matches(value, pattern) for pattern in patterns)


def _matches(value: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/").lstrip("./")
    return fnmatch.fnmatch(value, normalized) or Path(value).match(normalized)


def _family_name(pattern: str, value: str) -> str:
    prefix = pattern.replace("\\", "/").split("*")[0].rstrip("/")
    if prefix.startswith("**/") or not prefix:
        parts = value.split("/")
        if ".egg-info" in value:
            return next(("/".join(parts[: index + 1]) for index, part in enumerate(parts) if part.endswith(".egg-info")), parts[0])
        if "__pycache__" in parts:
            index = parts.index("__pycache__")
            return "/".join(parts[: index + 1])
        return parts[0]
    return prefix


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return ()
