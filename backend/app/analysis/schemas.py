from pydantic import BaseModel


class GraphNodeOut(BaseModel):
    id: str
    label: str
    language: str | None


class GraphEdgeOut(BaseModel):
    id: str
    source: str
    target: str


class DependencyGraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]