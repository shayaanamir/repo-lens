import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import ImportEdge
from app.repo.models import File


@dataclass
class GraphNode:
    id: str  # file_id as string — React Flow node ids are strings
    label: str  # file path, shown in the node
    language: str | None


@dataclass
class GraphEdge:
    id: str  # synthetic, e.g. "{source_id}-{target_id}"
    source: str
    target: str


@dataclass
class DependencyGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


async def build_dependency_graph(db: AsyncSession, repository_id: uuid.UUID) -> DependencyGraph:
    """
    Builds a file-level dependency graph for a repository: one node per
    file that participates in at least one import edge, and one edge
    per (source_file, target_file) import relationship.

    Files with no import edges at all (isolated files — e.g. standalone
    scripts, config, or files RepoLens couldn't parse) are intentionally
    left out of the graph; a node with no edges adds visual noise
    without conveying any relationship.
    """
    edges_result = await db.execute(
        select(ImportEdge.source_file_id, ImportEdge.target_file_id)
        .where(ImportEdge.repository_id == repository_id)
    )
    edge_rows = edges_result.all()

    if not edge_rows:
        return DependencyGraph(nodes=[], edges=[])

    file_ids_in_graph: set[uuid.UUID] = set()
    for source_id, target_id in edge_rows:
        file_ids_in_graph.add(source_id)
        file_ids_in_graph.add(target_id)

    files_result = await db.execute(
        select(File.id, File.path, File.language).where(File.id.in_(file_ids_in_graph))
    )
    file_rows = files_result.all()

    nodes = [
        GraphNode(id=str(file_id), label=path, language=language)
        for file_id, path, language in file_rows
    ]

    edges = [
        GraphEdge(
            id=f"{source_id}-{target_id}",
            source=str(source_id),
            target=str(target_id),
        )
        for source_id, target_id in edge_rows
    ]

    return DependencyGraph(nodes=nodes, edges=edges)