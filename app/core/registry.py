"""Node registry — lets the UI discover available node types and build graphs."""

from __future__ import annotations

from typing import Any

from app.core.graph import Node

_REGISTRY: dict[str, type[Node]] = {}


def register(cls: type[Node]) -> type[Node]:
    _REGISTRY[cls.type] = cls
    return cls


def get_node(node_type: str) -> type[Node]:
    if node_type not in _REGISTRY:
        raise KeyError(f"Unknown node type: {node_type!r}")
    return _REGISTRY[node_type]


def all_nodes() -> dict[str, type[Node]]:
    return dict(_REGISTRY)


def catalog() -> list[dict[str, Any]]:
    """Machine-readable description of every node type (for the canvas palette)."""
    out: list[dict[str, Any]] = []
    for node_type, cls in sorted(_REGISTRY.items(), key=lambda kv: (kv[1].category, kv[0])):
        params_schema: dict[str, Any] = {}
        if cls.params_model is not None:
            params_schema = cls.params_model.model_json_schema()
        out.append(
            {
                "type": node_type,
                "title": cls.title,
                "category": cls.category,
                "description": cls.description,
                "inputs": cls.inputs,
                "outputs": cls.outputs,
                "params_schema": params_schema,
            }
        )
    return out
