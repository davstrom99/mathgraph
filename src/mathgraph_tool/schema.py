"""Pydantic schema for mathgraph YAML files."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NodeKind(str, Enum):
    VARIABLE = "variable"
    ASSUMPTION = "assumption"
    OBJECTIVE = "objective"
    ESTIMATOR = "estimator"
    APPROXIMATION = "approximation"
    SIMULATOR = "simulator"
    VALIDATION = "validation"
    EXPERIMENT = "experiment"
    FIGURE = "figure"
    DATASET = "dataset"
    TEST = "test"


class EdgeKind(str, Enum):
    DEFINES = "defines"
    ASSUMES = "assumes"
    DEPENDS_ON = "depends_on"
    DERIVES = "derives"
    IMPLEMENTS = "implements"
    APPROXIMATES = "approximates"
    VALIDATES = "validates"
    TESTS = "tests"
    GENERATES = "generates"
    USES = "uses"
    AFFECTS = "affects"


class TexRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    label: str


class CodeRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    symbol: str | None = None
    line: int | None = Field(default=None, ge=1)
    role: str | None = Field(
        default=None,
        pattern="^(definition|implementation|caller|test|experiment|configuration)$",
    )


class OutputRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    tex_root: str
    repo_root: str = "."
    code_roots: list[str] = Field(default_factory=list)
    code_exclude: list[str] = Field(default_factory=list)


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: NodeKind
    title: str
    statement: str
    display_label: str | None = None
    symbol: str | None = None
    uses: list[str] | None = None
    tex: TexRef | None = None
    code: list[CodeRef] = Field(default_factory=list)
    outputs: list[OutputRef] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def id_must_be_namespaced(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("node id must be namespaced, for example `model.gaussian_observation`")
        return value


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: str = Field(alias="from")
    to: str
    kind: EdgeKind
    description: str
    tex: TexRef


class GraphSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project: Project
    nodes: list[Node]
    edges: list[Edge]

    @model_validator(mode="after")
    def validate_unique_ids_and_endpoints(self) -> "GraphSpec":
        node_ids = [node.id for node in self.nodes]
        duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate node ids: {', '.join(duplicates)}")

        node_id_set = set(node_ids)
        bad_edges: list[str] = []
        for edge in self.edges:
            if edge.from_ not in node_id_set:
                bad_edges.append(f"{edge.from_} --{edge.kind.value}--> {edge.to}: missing source")
            if edge.to not in node_id_set:
                bad_edges.append(f"{edge.from_} --{edge.kind.value}--> {edge.to}: missing target")
        if bad_edges:
            raise ValueError("edge endpoint errors: " + "; ".join(bad_edges))
        return self

    @property
    def node_by_id(self) -> dict[str, Node]:
        return {node.id: node for node in self.nodes}

    def all_tex_refs(self) -> list[tuple[str, TexRef]]:
        refs: list[tuple[str, TexRef]] = []
        for node in self.nodes:
            if node.tex is not None:
                refs.append((f"node {node.id}", node.tex))
        for index, edge in enumerate(self.edges, start=1):
            refs.append((f"edge {index} {edge.from_}->{edge.to}", edge.tex))
        return refs

    def all_code_refs(self) -> list[tuple[str, CodeRef]]:
        refs: list[tuple[str, CodeRef]] = []
        for node in self.nodes:
            for ref in node.code:
                refs.append((f"node {node.id}", ref))
        return refs

    def model_dump_for_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)
