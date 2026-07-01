from pathlib import Path

import tomllib


def test_python_310_declares_tomllib_backport():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "tomli>=2.0; python_version < '3.11'" in project["project"]["dependencies"]


def test_indexer_falls_back_to_tomli_on_python_310():
    source = Path("src/mathgraph_tool/indexing.py").read_text(encoding="utf-8-sig")

    assert "except ModuleNotFoundError" in source
    assert "import tomli as tomllib" in source
