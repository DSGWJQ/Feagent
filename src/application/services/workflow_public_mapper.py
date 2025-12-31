"""Workflow entity to public dict mapper.

Maps Domain Workflow entity to a JSON-friendly dict for external consumers.
This mapper lives in Application layer to avoid Interface DTO dependencies.

Field name mappings (Domain -> Public):
- node.config -> data
- edge.source_node_id -> source
- edge.target_node_id -> target
- status enum -> string value
"""

from __future__ import annotations

from typing import Any

from src.domain.entities.workflow import Workflow


class WorkflowPublicMapper:
    """Maps Workflow entities to public JSON-friendly dicts.

    Usage:
        mapper = WorkflowPublicMapper()
        workflow_dict = mapper.to_dict(workflow_entity)

    The output dict matches the frontend's expected Workflow structure.
    """

    def to_dict(self, workflow: Workflow) -> dict[str, Any]:
        """Convert Workflow entity to public dict format.

        Args:
            workflow: Domain Workflow entity

        Returns:
            Dict with frontend-compatible field names:
            - nodes[].data (not config)
            - edges[].source/target (not source_node_id/target_node_id)
            - status as string value
        """
        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "nodes": [self._map_node(node) for node in workflow.nodes],
            "edges": [self._map_edge(edge) for edge in workflow.edges],
            "status": workflow.status.value
            if hasattr(workflow.status, "value")
            else str(workflow.status),
            "project_id": getattr(workflow, "project_id", None),
            "created_at": self._serialize_datetime(workflow.created_at),
            "updated_at": self._serialize_datetime(workflow.updated_at),
        }

    def _map_node(self, node: Any) -> dict[str, Any]:
        """Map a single node to public format."""
        position = {"x": 0, "y": 0}
        if hasattr(node, "position") and node.position:
            position = {"x": node.position.x, "y": node.position.y}

        node_type = node.type.value if hasattr(node.type, "value") else str(node.type)

        return {
            "id": node.id,
            "type": node_type,
            "name": getattr(node, "name", ""),
            "data": getattr(node, "config", {}),
            "position": position,
        }

    def _map_edge(self, edge: Any) -> dict[str, Any]:
        """Map a single edge to public format."""
        return {
            "id": edge.id,
            "source": edge.source_node_id,
            "target": edge.target_node_id,
            "condition": getattr(edge, "condition", None),
        }

    def _serialize_datetime(self, dt: Any) -> str | None:
        """Serialize datetime to ISO string."""
        if dt is None:
            return None
        if hasattr(dt, "isoformat"):
            return dt.isoformat()
        return str(dt)
