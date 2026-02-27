from typing import Literal, Optional

from pydantic import BaseModel


class DiagramGroup(BaseModel):
    id: str
    label: str
    color: str = "#6366f1"


class DiagramNode(BaseModel):
    id: str
    label: str
    type: Literal["module", "service", "database", "external"]
    x: float = 0.0
    y: float = 0.0
    description: Optional[str] = None
    is_overridden: bool = False
    file_path: Optional[str] = None
    group_id: Optional[str] = None


class DiagramEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    type: Literal["dependency", "data_flow", "api_call"] = "dependency"


class DiagramSnapshot(BaseModel):
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]
    groups: list[DiagramGroup] = []


class RequirementsIn(BaseModel):
    requirements_text: str


class IncomingMessage(BaseModel):
    type: Literal["chat", "override_node", "override_edge"]
    content: Optional[str] = None
    diagram_context: Optional[DiagramSnapshot] = None
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    patch: Optional[dict] = None


class DiagramVersionOut(BaseModel):
    id: str
    label: str
    created_at: str


class DiagramVersionListOut(BaseModel):
    versions: list[DiagramVersionOut]


class DiagramRestoreOut(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    groups: list[dict] = []
